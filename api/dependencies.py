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
from typing import Optional

from fastapi import Depends, HTTPException, Header
from supabase import create_client, Client

from app.utils.logger import get_logger

logger = get_logger(__name__)

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


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    supabase: Client = Depends(get_supabase),
) -> str:
    """
    Verifies the Supabase JWT from the Authorization header.
    Returns the user_id (UUID string).

    Raises 401 if token is missing or invalid.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]

    try:
        # Supabase SDK verifies the JWT and returns user info
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return str(response.user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Auth verification failed: {e}")
        raise HTTPException(status_code=401, detail="Token verification failed")


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
    supabase: Client = Depends(get_supabase),
) -> Optional[str]:
    """
    Same as get_current_user but returns None instead of raising 401.
    Use for endpoints that support both authenticated and guest access.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split(" ", 1)[1]
        response = supabase.auth.get_user(token)
        if response and response.user:
            return str(response.user.id)
        return None
    except Exception:
        return None
