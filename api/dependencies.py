"""
api/dependencies.py
───────────────────
Shared FastAPI dependencies:
  - Supabase admin client (for DB reads/writes from the backend)
  - get_current_user() — verifies Supabase JWT and returns user_id
  - Optional auth for guest-mode endpoints

The frontend sends:
    Authorization: Bearer <supabase_access_token>

We verify it with the Supabase admin client (service role key).
"""

import os
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Header, Request
from supabase import create_client, Client

from app.config import GUEST_READ_ONLY_MODE
from app.utils.logger import get_logger

logger = get_logger(__name__)

_AUTH_ERROR_KEY = "_auth_error"


def _classify_auth_error(exc: Exception) -> str:
    """Map auth exceptions to coarse error types consumed by get_current_user."""
    text = str(exc).lower()
    if "token is expired" in text or "expired" in text:
        return "expired"
    return "invalid"

# ── Supabase client (module-level singleton) ──────────────────────────────────
# Uses the SERVICE ROLE key — never expose this in the frontend.
# Set in .env:
#   SUPABASE_URL=https://xxxx.supabase.co
#   SUPABASE_SERVICE_KEY=eyJ...
_supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    global _supabase_client
    if _supabase_client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        _supabase_client = create_client(str(url), str(key))
    return _supabase_client


def _to_user_payload(user_obj: Any) -> Dict[str, Any]:
    if isinstance(user_obj, dict):
        return dict(user_obj)

    data = getattr(user_obj, "__dict__", None)
    if isinstance(data, dict):
        return dict(data)

    payload: Dict[str, Any] = {}
    for key in ("id", "email", "is_anonymous"):
        payload[key] = getattr(user_obj, key, None)
    return payload


async def get_authenticated_user(
    authorization: Optional[str] = Header(default=None),
    supabase: Client = Depends(get_supabase),
) -> Optional[Dict[str, Any]]:
    """Return verified Supabase user payload or None when not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        response = supabase.auth.get_user(token)
        if response and response.user:
            return _to_user_payload(response.user)
    except Exception as e:
        logger.warning(f"Auth verification failed: {e}")
        return {_AUTH_ERROR_KEY: _classify_auth_error(e)}
    return None


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_user(
    auth_user: Optional[Dict[str, Any]] = Depends(get_authenticated_user),
) -> str:
    """
    Verifies the Supabase JWT from the Authorization header.
    Returns the user_id (UUID string).

    Raises 401 if token is missing, malformed, invalid, or expired.
    """
    if not auth_user:
        raise HTTPException(status_code=401, detail="Token verification failed")

    auth_error = auth_user.get(_AUTH_ERROR_KEY)
    if auth_error == "expired":
        raise HTTPException(status_code=401, detail="Token expired. Please sign in again.")
    if auth_error:
        raise HTTPException(status_code=401, detail="Token verification failed")

    user_id = auth_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token verification failed")

    return str(user_id)


async def get_optional_user(
    auth_user: Optional[Dict[str, Any]] = Depends(get_authenticated_user),
) -> Optional[str]:
    """
    Same as get_current_user but returns None instead of raising 401.
    Use for endpoints that support both authenticated and guest access.
    """
    if not auth_user:
        return None
    user_id = auth_user.get("id")
    return str(user_id) if user_id else None


async def enforce_guest_read_only(
    request: Request,
    auth_user: Optional[Dict[str, Any]] = Depends(get_authenticated_user),
) -> None:
    """
    Feature-flagged guard: when enabled, guest users cannot mutate resources.
    Safe by default because the flag is disabled unless explicitly configured.
    """
    if not GUEST_READ_ONLY_MODE:
        return

    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    if auth_user and bool(auth_user.get("is_anonymous")):
        raise HTTPException(
            status_code=403,
            detail="Guest sessions are read-only. Please sign in to continue.",
        )
