"""
api/services/auth_service.py
────────────────────────────
Auth and identity helper logic for validation, account-state tracking,
audit logging, and session history.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Request
from supabase import Client

from app.config import AUTH_MAX_FAILED_LOGINS, AUTH_LOCKOUT_MINUTES, AUTH_REQUIRE_EMAIL_VERIFICATION
from app.utils.logger import get_logger

logger = get_logger(__name__)

_EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MISSING_AUTH_TABLE_WARNED: set[str] = set()
_BROWSER_HINTS = (
    ("edge", "Edge"),
    ("edg", "Edge"),
    ("chrome", "Chrome"),
    ("firefox", "Firefox"),
    ("safari", "Safari"),
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value:
        raise ValueError("Email is required.")
    if len(value) > 320:
        raise ValueError("Email address is too long.")
    if not _EMAIL_REGEX.match(value):
        raise ValueError("Enter a valid email address.")
    return value


def validate_password(password: str) -> None:
    value = password or ""
    if not value.strip():
        raise ValueError("Password is required.")
    if len(value) < 8:
        raise ValueError("Use at least 8 characters.")
    if len(value) > 128:
        raise ValueError("Password must be 128 characters or fewer.")


def _safe_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _user_to_dict(user_obj: Any) -> Dict[str, Any]:
    if isinstance(user_obj, dict):
        return dict(user_obj)

    data = getattr(user_obj, "__dict__", None)
    if isinstance(data, dict):
        return dict(data)

    out: Dict[str, Any] = {}
    for key in (
        "id",
        "email",
        "identities",
        "app_metadata",
        "user_metadata",
        "email_confirmed_at",
        "banned_until",
        "is_anonymous",
    ):
        out[key] = getattr(user_obj, key, None)
    return out


def _extract_provider(identity: Dict[str, Any]) -> str:
    provider = str(identity.get("provider") or "").strip().lower()
    if not provider:
        provider = str(identity.get("idp") or "").strip().lower()
    if provider in {"github", "google", "azure", "anonymous", "email", "password"}:
        return "password" if provider == "email" else provider
    return "other"


def list_identity_providers(user_payload: Dict[str, Any]) -> List[str]:
    providers = set()
    identities = user_payload.get("identities") or []
    if isinstance(identities, list):
        for item in identities:
            if isinstance(item, dict):
                providers.add(_extract_provider(item))
    app_metadata = user_payload.get("app_metadata") or {}
    provider = str((app_metadata.get("provider") if isinstance(app_metadata, dict) else "") or "").strip().lower()
    if provider:
        providers.add("password" if provider == "email" else provider)
    providers.discard("")
    return sorted(providers)


def extract_client_context(request: Request) -> Dict[str, Optional[str]]:
    user_agent = request.headers.get("user-agent", "")
    lowered = user_agent.lower()

    browser = "Unknown"
    for marker, label in _BROWSER_HINTS:
        if marker in lowered:
            browser = label
            break

    os_name = "Unknown"
    if "windows" in lowered:
        os_name = "Windows"
    elif "mac os" in lowered or "macintosh" in lowered:
        os_name = "macOS"
    elif "linux" in lowered:
        os_name = "Linux"
    elif "android" in lowered:
        os_name = "Android"
    elif "iphone" in lowered or "ipad" in lowered:
        os_name = "iOS"

    device = "Desktop"
    if any(token in lowered for token in ("iphone", "ipad", "android", "mobile")):
        device = "Mobile"

    forwarded_for = request.headers.get("x-forwarded-for", "")
    ip_address = (forwarded_for.split(",", 1)[0].strip() if forwarded_for else None) or (
        request.client.host if request.client else None
    )

    return {
        "ip_address": ip_address,
        "user_agent": user_agent or None,
        "browser": browser,
        "os": os_name,
        "device": device,
    }


def _safe_insert(table_query: Any, payload: Dict[str, Any]) -> None:
    try:
        table_query.insert(payload).execute()
    except Exception as e:
        table_name = _missing_auth_table_name(e)
        if table_name:
            _warn_missing_auth_table_once(table_name)
            return
        logger.warning(f"Auth persistence insert failed: {e}")


def _missing_auth_table_name(err: Exception) -> Optional[str]:
    msg = str(err).lower()
    if "pgrst205" not in msg and "schema cache" not in msg and "could not find the table" not in msg:
        return None

    for table_name in (
        "auth_audit_logs",
        "auth_login_history",
        "auth_account_state",
        "auth_identity_links",
    ):
        if table_name in msg:
            return table_name
    return None


def _warn_missing_auth_table_once(table_name: str) -> None:
    if table_name in _MISSING_AUTH_TABLE_WARNED:
        return
    _MISSING_AUTH_TABLE_WARNED.add(table_name)
    logger.warning(
        f"Auth persistence table '{table_name}' is missing in Supabase schema cache. "
        "Apply auth identity migration to enable audit/session persistence."
    )


def record_audit_log(
    supabase: Client,
    *,
    action: str,
    outcome: str,
    request: Request,
    user_id: Optional[str] = None,
    email_normalized: Optional[str] = None,
    provider: Optional[str] = None,
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    context = extract_client_context(request)
    payload = {
        "user_id": user_id,
        "email_normalized": email_normalized,
        "action": action,
        "outcome": outcome,
        "provider": provider,
        "reason": reason,
        "ip_address": context.get("ip_address"),
        "browser": context.get("browser"),
        "os": context.get("os"),
        "device": context.get("device"),
        "user_agent": context.get("user_agent"),
        "metadata": metadata or {},
        "created_at": utcnow_iso(),
    }
    _safe_insert(supabase.table("auth_audit_logs"), payload)


def _safe_table_first(supabase: Client, table_name: str, **filters: Any) -> Optional[Dict[str, Any]]:
    try:
        q = supabase.table(table_name).select("*").limit(1)
        for key, value in filters.items():
            q = q.eq(key, value)
        result = q.execute()
        data = getattr(result, "data", None)
        if isinstance(data, list) and data:
            return data[0]
    except Exception:
        return None
    return None


def get_account_state_by_email(supabase: Client, email_normalized: str) -> Optional[Dict[str, Any]]:
    return _safe_table_first(supabase, "auth_account_state", email_normalized=email_normalized)


def upsert_account_state(
    supabase: Client,
    *,
    user_id: Optional[str],
    email_normalized: str,
    account_status: str = "active",
    failed_login_attempts: Optional[int] = None,
    locked_until: Optional[str] = None,
    last_login_at: Optional[str] = None,
    last_logout_at: Optional[str] = None,
) -> None:
    payload: Dict[str, Any] = {
        "email_normalized": email_normalized,
        "account_status": account_status,
        "updated_at": utcnow_iso(),
    }
    if user_id:
        payload["user_id"] = user_id
    if failed_login_attempts is not None:
        payload["failed_login_attempts"] = failed_login_attempts
    if locked_until is not None:
        payload["locked_until"] = locked_until
    if last_login_at is not None:
        payload["last_login_at"] = last_login_at
    if last_logout_at is not None:
        payload["last_logout_at"] = last_logout_at

    try:
        supabase.table("auth_account_state").upsert(payload, on_conflict="email_normalized").execute()
    except Exception as e:
        table_name = _missing_auth_table_name(e)
        if table_name:
            _warn_missing_auth_table_once(table_name)
            return
        logger.warning(f"Failed to upsert auth_account_state: {e}")


def _list_supabase_users(supabase: Client, *, max_pages: int = 5, per_page: int = 200) -> List[Dict[str, Any]]:
    users: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        try:
            response = supabase.auth.admin.list_users(page=page, per_page=per_page)
        except TypeError:
            response = supabase.auth.admin.list_users()
        except Exception as e:
            logger.warning(f"Failed listing users from Supabase Auth: {e}")
            break

        page_users = getattr(response, "users", None)
        if page_users is None and isinstance(response, dict):
            page_users = response.get("users")
        if not isinstance(page_users, list) or not page_users:
            break

        users.extend(_user_to_dict(item) for item in page_users)
        if len(page_users) < per_page:
            break
    return users


def find_auth_user_by_email(supabase: Client, email_normalized: str) -> Optional[Dict[str, Any]]:
    users = _list_supabase_users(supabase)
    for user in users:
        email = str(user.get("email") or "").strip().lower()
        if email == email_normalized:
            return user
    return None


def record_identity_links_for_user(supabase: Client, user_payload: Dict[str, Any], email_normalized: str) -> None:
    user_id = str(user_payload.get("id") or "")
    if not user_id:
        return

    identities = user_payload.get("identities") or []
    if not isinstance(identities, list) or not identities:
        providers = list_identity_providers(user_payload)
        if not providers:
            providers = ["password"]
        for provider in providers:
            try:
                supabase.table("auth_identity_links").upsert(
                    {
                        "user_id": user_id,
                        "email_normalized": email_normalized,
                        "provider": provider,
                        "updated_at": utcnow_iso(),
                    },
                    on_conflict="user_id,provider",
                ).execute()
            except Exception as e:
                table_name = _missing_auth_table_name(e)
                if table_name:
                    _warn_missing_auth_table_once(table_name)
                    return
                logger.warning(f"Failed to upsert identity link ({provider}): {e}")
        return

    for identity in identities:
        if not isinstance(identity, dict):
            continue
        provider = _extract_provider(identity)
        provider_user_id = identity.get("id") or identity.get("user_id")
        identity_data = identity.get("identity_data") if isinstance(identity.get("identity_data"), dict) else {}
        provider_verified = identity_data.get("email_verified")
        try:
            supabase.table("auth_identity_links").upsert(
                {
                    "user_id": user_id,
                    "email_normalized": email_normalized,
                    "provider": provider,
                    "provider_user_id": str(provider_user_id) if provider_user_id else None,
                    "provider_email_verified": bool(provider_verified) if provider_verified is not None else None,
                    "updated_at": utcnow_iso(),
                },
                on_conflict="user_id,provider",
            ).execute()
        except Exception as e:
            table_name = _missing_auth_table_name(e)
            if table_name:
                _warn_missing_auth_table_once(table_name)
                return
            logger.warning(f"Failed to upsert identity link ({provider}): {e}")


def check_account_lock(state: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    if not state:
        return False, None

    locked_until = _safe_iso(state.get("locked_until"))
    if locked_until and locked_until > datetime.now(timezone.utc):
        return True, locked_until.isoformat()

    status = str(state.get("account_status") or "active").lower()
    if status in {"disabled", "deleted", "locked"} and locked_until is None:
        return True, None

    return False, None


def register_login_failure(supabase: Client, email_normalized: str, user_id: Optional[str]) -> Optional[str]:
    state = get_account_state_by_email(supabase, email_normalized) or {}
    failed_attempts = int(state.get("failed_login_attempts") or 0) + 1

    locked_until: Optional[str] = None
    if failed_attempts >= AUTH_MAX_FAILED_LOGINS:
        locked_until = (datetime.now(timezone.utc) + timedelta(minutes=AUTH_LOCKOUT_MINUTES)).isoformat()

    upsert_account_state(
        supabase,
        user_id=user_id,
        email_normalized=email_normalized,
        account_status="locked" if locked_until else "active",
        failed_login_attempts=failed_attempts,
        locked_until=locked_until,
    )
    return locked_until


def register_login_success(supabase: Client, email_normalized: str, user_id: Optional[str]) -> None:
    upsert_account_state(
        supabase,
        user_id=user_id,
        email_normalized=email_normalized,
        account_status="active",
        failed_login_attempts=0,
        locked_until="",
        last_login_at=utcnow_iso(),
    )


def record_login_history(
    supabase: Client,
    *,
    request: Request,
    user_id: Optional[str],
    email_normalized: str,
    provider: str,
    success: bool,
    session_id: Optional[str] = None,
    failure_reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    context = extract_client_context(request)
    _safe_insert(
        supabase.table("auth_login_history"),
        {
            "user_id": user_id,
            "email_normalized": email_normalized,
            "provider": provider,
            "session_id": session_id,
            "ip_address": context.get("ip_address"),
            "browser": context.get("browser"),
            "os": context.get("os"),
            "device": context.get("device"),
            "user_agent": context.get("user_agent"),
            "success": success,
            "failure_reason": failure_reason,
            "metadata": metadata or {},
            "login_at": utcnow_iso(),
        },
    )


def mark_logout(
    supabase: Client,
    *,
    user_id: Optional[str],
    email_normalized: Optional[str],
    session_id: Optional[str],
) -> None:
    logout_at = utcnow_iso()
    try:
        query = supabase.table("auth_login_history").update({"logout_at": logout_at})
        if session_id:
            query = query.eq("session_id", session_id)
        elif user_id:
            query = query.eq("user_id", user_id)
        elif email_normalized:
            query = query.eq("email_normalized", email_normalized)
        else:
            return
        query.execute()
    except Exception as e:
        table_name = _missing_auth_table_name(e)
        if table_name:
            _warn_missing_auth_table_once(table_name)
            return
        logger.warning(f"Failed to mark logout in history: {e}")

    if user_id and email_normalized:
        upsert_account_state(
            supabase,
            user_id=user_id,
            email_normalized=email_normalized,
            account_status="active",
            last_logout_at=logout_at,
        )


def get_recent_sessions(supabase: Client, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("auth_login_history")
            .select("id,provider,success,login_at,logout_at,browser,os,device,ip_address")
            .eq("user_id", user_id)
            .order("login_at", desc=True)
            .limit(max(1, min(limit, 100)))
            .execute()
        )
        rows = getattr(result, "data", None)
        if isinstance(rows, list):
            return rows
    except Exception as e:
        table_name = _missing_auth_table_name(e)
        if table_name:
            _warn_missing_auth_table_once(table_name)
            return []
        logger.warning(f"Failed to load recent sessions: {e}")
    return []


def evaluate_login_preflight(supabase: Client, email_normalized: str) -> Dict[str, Any]:
    state = get_account_state_by_email(supabase, email_normalized)
    is_locked, locked_until = check_account_lock(state)
    if is_locked:
        return {
            "ok": False,
            "message": "Too many unsuccessful login attempts. Please try again later.",
            "locked_until": locked_until,
            "providers": [],
        }

    user_payload = find_auth_user_by_email(supabase, email_normalized)
    if not user_payload:
        return {
            "ok": False,
            "message": "No account was found for this email address.",
            "locked_until": None,
            "providers": [],
        }

    banned_until = _safe_iso(user_payload.get("banned_until"))
    if banned_until and banned_until > datetime.now(timezone.utc):
        return {
            "ok": False,
            "message": "This account has been disabled. Please contact your administrator.",
            "locked_until": banned_until.isoformat(),
            "providers": [],
        }

    if AUTH_REQUIRE_EMAIL_VERIFICATION and not user_payload.get("email_confirmed_at"):
        return {
            "ok": False,
            "message": "Please verify your email address before signing in.",
            "locked_until": None,
            "providers": list_identity_providers(user_payload),
        }

    user_id = str(user_payload.get("id") or "")
    if user_id:
        upsert_account_state(
            supabase,
            user_id=user_id,
            email_normalized=email_normalized,
            account_status="active",
        )

    providers = list_identity_providers(user_payload)
    record_identity_links_for_user(supabase, user_payload, email_normalized)

    return {
        "ok": True,
        "message": "Credentials accepted. Continue signing in.",
        "locked_until": None,
        "providers": providers,
        "user_id": user_id or None,
    }
