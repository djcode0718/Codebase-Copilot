"""
api/routers/auth.py
───────────────────
Authentication management endpoints for preflight validation, audit logging,
oauth identity linking, and recent session visibility.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import Client

from api.dependencies import get_current_user, get_optional_user, get_supabase
from api.models.auth import (
    GenericAuthResponse,
    LoginAuditRequest,
    LoginPreflightRequest,
    LoginPreflightResponse,
    LogoutAuditRequest,
    OAuthLinkRequest,
    PasswordResetAuditRequest,
    PasswordResetCompleteAuditRequest,
    RegisterPreflightRequest,
    RegisterPreflightResponse,
    SessionHistoryItem,
    SessionHistoryResponse,
)
from api.services import auth_service
from app.config import AUTH_LOGIN_HISTORY_LIMIT, AUTH_RATE_LIMIT_PER_MINUTE

router = APIRouter()

_RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_lock = threading.Lock()
_rate_limit_buckets: Dict[str, Deque[float]] = defaultdict(deque)


def _rate_limit_key(request: Request, route_key: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (forwarded.split(",", 1)[0].strip() if forwarded else None) or (request.client.host if request.client else "unknown")
    return f"{route_key}:{ip}"


def _enforce_rate_limit(request: Request, route_key: str) -> None:
    key = _rate_limit_key(request, route_key)
    now = time.time()

    with _rate_limit_lock:
        bucket = _rate_limit_buckets[key]
        while bucket and (now - bucket[0]) > _RATE_LIMIT_WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= AUTH_RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=429,
                detail="Too many authentication requests. Please wait and try again.",
            )

        bucket.append(now)


@router.post("/register/preflight", response_model=RegisterPreflightResponse)
async def register_preflight(
    body: RegisterPreflightRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    _enforce_rate_limit(request, "register-preflight")

    try:
        normalized_email = auth_service.normalize_email(body.email)
        auth_service.validate_password(body.password)
    except ValueError as e:
        return RegisterPreflightResponse(
            ok=False,
            email=(body.email or "").strip().lower(),
            message=str(e),
            providers=[],
        )

    existing_user = auth_service.find_auth_user_by_email(supabase, normalized_email)
    if existing_user:
        providers = auth_service.list_identity_providers(existing_user)
        auth_service.record_identity_links_for_user(supabase, existing_user, normalized_email)
        auth_service.record_audit_log(
            supabase,
            action="register_preflight",
            outcome="blocked_duplicate",
            request=request,
            email_normalized=normalized_email,
            reason="email_already_registered",
            provider=providers[0] if providers else "password",
            metadata={"providers": providers},
        )
        return RegisterPreflightResponse(
            ok=False,
            email=normalized_email,
            providers=providers,
            message=(
                "This email is already registered with Codebase Copilot. "
                "Please sign in using your existing account."
            ),
        )

    auth_service.record_audit_log(
        supabase,
        action="register_preflight",
        outcome="allowed",
        request=request,
        email_normalized=normalized_email,
    )
    return RegisterPreflightResponse(
        ok=True,
        email=normalized_email,
        message="Email is available.",
        providers=[],
    )


@router.post("/login/preflight", response_model=LoginPreflightResponse)
async def login_preflight(
    body: LoginPreflightRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    _enforce_rate_limit(request, "login-preflight")

    try:
        normalized_email = auth_service.normalize_email(body.email)
    except ValueError as e:
        return LoginPreflightResponse(
            ok=False,
            email=(body.email or "").strip().lower(),
            message=str(e),
            providers=[],
            locked_until=None,
        )

    result = auth_service.evaluate_login_preflight(supabase, normalized_email)
    auth_service.record_audit_log(
        supabase,
        action="login_preflight",
        outcome="allowed" if result.get("ok") else "denied",
        request=request,
        email_normalized=normalized_email,
        reason=None if result.get("ok") else "preflight_denied",
        metadata={"providers": result.get("providers") or []},
    )

    return LoginPreflightResponse(
        ok=bool(result.get("ok")),
        email=normalized_email,
        message=str(result.get("message") or "Unable to validate sign-in."),
        providers=list(result.get("providers") or []),
        locked_until=result.get("locked_until"),
    )


@router.post("/login/audit", response_model=GenericAuthResponse)
async def login_audit(
    body: LoginAuditRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    _enforce_rate_limit(request, "login-audit")

    try:
        normalized_email = auth_service.normalize_email(body.email)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid email address")

    preflight = auth_service.evaluate_login_preflight(supabase, normalized_email)
    user_id: Optional[str] = preflight.get("user_id") if isinstance(preflight, dict) else None

    provider = (body.provider or "password").strip().lower() or "password"
    if body.success:
        auth_service.register_login_success(supabase, normalized_email, user_id)
    else:
        locked_until = auth_service.register_login_failure(supabase, normalized_email, user_id)
        if locked_until and not body.failure_reason:
            body.failure_reason = "too_many_attempts"

    auth_service.record_login_history(
        supabase,
        request=request,
        user_id=user_id,
        email_normalized=normalized_email,
        provider=provider,
        success=body.success,
        session_id=body.session_id,
        failure_reason=body.failure_reason,
        metadata={"remember_me": body.remember_me, **(body.metadata or {})},
    )

    auth_service.record_audit_log(
        supabase,
        action="login",
        outcome="success" if body.success else "failure",
        request=request,
        user_id=user_id,
        email_normalized=normalized_email,
        provider=provider,
        reason=body.failure_reason,
        metadata={"session_id": body.session_id},
    )

    return GenericAuthResponse(message="Authentication event recorded.")


@router.post("/logout/audit", response_model=GenericAuthResponse)
async def logout_audit(
    body: LogoutAuditRequest,
    request: Request,
    user_id: Optional[str] = Depends(get_optional_user),
    supabase: Client = Depends(get_supabase),
):
    normalized_email: Optional[str] = None
    if body.email:
        try:
            normalized_email = auth_service.normalize_email(body.email)
        except ValueError:
            normalized_email = None

    auth_service.mark_logout(
        supabase,
        user_id=user_id,
        email_normalized=normalized_email,
        session_id=body.session_id,
    )

    auth_service.record_audit_log(
        supabase,
        action="logout_all" if body.all_devices else "logout",
        outcome="success",
        request=request,
        user_id=user_id,
        email_normalized=normalized_email,
        metadata={"all_devices": body.all_devices, "session_id": body.session_id},
    )

    return GenericAuthResponse(message="Logout event recorded.")


@router.post("/password-reset/audit-request", response_model=GenericAuthResponse)
async def password_reset_audit_request(
    body: PasswordResetAuditRequest,
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    _enforce_rate_limit(request, "password-reset-request")

    # Intentionally generic: do not leak account existence.
    try:
        normalized_email = auth_service.normalize_email(body.email)
    except ValueError:
        normalized_email = None

    auth_service.record_audit_log(
        supabase,
        action="password_reset_request",
        outcome="accepted",
        request=request,
        email_normalized=normalized_email,
    )
    return GenericAuthResponse(message="If an account exists, reset instructions have been sent.")


@router.post("/password-reset/audit-complete", response_model=GenericAuthResponse)
async def password_reset_audit_complete(
    body: PasswordResetCompleteAuditRequest,
    request: Request,
    user_id: Optional[str] = Depends(get_optional_user),
    supabase: Client = Depends(get_supabase),
):
    normalized_email = None
    if body.email:
        try:
            normalized_email = auth_service.normalize_email(body.email)
        except ValueError:
            normalized_email = None

    auth_service.record_audit_log(
        supabase,
        action="password_reset_complete",
        outcome="success" if body.success else "failure",
        request=request,
        user_id=user_id,
        email_normalized=normalized_email,
    )

    return GenericAuthResponse(message="Password reset event recorded.")


@router.post("/oauth/link", response_model=GenericAuthResponse)
async def oauth_link_identity(
    body: OAuthLinkRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        response = supabase.auth.admin.get_user_by_id(user_id)
        user_obj = getattr(response, "user", None)
        user_payload = auth_service._user_to_dict(user_obj) if user_obj is not None else {}
        email_normalized = auth_service.normalize_email(str(user_payload.get("email") or ""))
        auth_service.record_identity_links_for_user(supabase, user_payload, email_normalized)
        auth_service.upsert_account_state(
            supabase,
            user_id=user_id,
            email_normalized=email_normalized,
            account_status="active",
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Authenticated account has no valid email")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Unable to link OAuth identity") from e

    auth_service.record_audit_log(
        supabase,
        action="oauth_link",
        outcome="success",
        request=request,
        user_id=user_id,
        email_normalized=email_normalized,
        provider=body.provider,
    )

    return GenericAuthResponse(message="Identity provider linked.")


@router.get("/sessions", response_model=SessionHistoryResponse)
async def list_recent_sessions(
    limit: int = AUTH_LOGIN_HISTORY_LIMIT,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    rows = auth_service.get_recent_sessions(supabase, user_id=user_id, limit=limit)
    return SessionHistoryResponse(sessions=[SessionHistoryItem(**row) for row in rows])
