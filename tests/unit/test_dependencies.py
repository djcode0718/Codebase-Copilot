"""
tests/test_dependencies.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Unit tests for api/dependencies.py:
  - get_supabase()
  - get_current_user()
  - get_optional_user()
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from starlette.requests import Request


# â”€â”€â”€ get_supabase â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetSupabase:
    def test_raises_if_env_not_set(self):
        """Should raise RuntimeError when env vars are missing."""
        import importlib
        import api.dependencies as dep_module

        # Reset the module-level singleton so the factory runs fresh
        original = dep_module._supabase_client
        dep_module._supabase_client = None

        with (
            patch.dict(os.environ, {}, clear=True),  # wipe env
            patch("api.dependencies.create_client") as mock_create,
        ):
            with pytest.raises(RuntimeError, match="SUPABASE_URL"):
                dep_module.get_supabase()

        dep_module._supabase_client = original  # restore

    def test_returns_singleton(self):
        """Returns same client on second call without re-creating."""
        import api.dependencies as dep_module

        fake_client = MagicMock()
        dep_module._supabase_client = fake_client

        result = dep_module.get_supabase()
        assert result is fake_client

        dep_module._supabase_client = None  # reset

    def test_creates_client_with_env(self):
        import api.dependencies as dep_module

        dep_module._supabase_client = None

        fake_client = MagicMock()
        with (
            patch.dict(os.environ, {
                "SUPABASE_URL": "https://fake.supabase.co",
                "SUPABASE_SERVICE_KEY": "fake-key",
            }),
            patch("api.dependencies.create_client", return_value=fake_client) as mock_create,
        ):
            result = dep_module.get_supabase()
            mock_create.assert_called_once_with("https://fake.supabase.co", "fake-key")
            assert result is fake_client

        dep_module._supabase_client = None  # reset


# â”€â”€â”€ get_current_user â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetCurrentUser:
    """Async dependency â€” call with asyncio.run or pytest-asyncio."""

    @pytest.mark.asyncio
    async def test_no_auth_header_raises_401(self):
        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(auth_user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_header_raises_401(self):
        from api.dependencies import get_current_user
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(auth_user={})
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self):
        from api.dependencies import get_current_user

        result = await get_current_user(auth_user={"id": "user-uuid-123"})
        assert result == "user-uuid-123"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(auth_user=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Expired tokens must not be accepted by backend dependencies."""
        from api.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(auth_user=None)
        assert exc_info.value.status_code == 401


# â”€â”€â”€ get_optional_user â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetOptionalUser:
    @pytest.mark.asyncio
    async def test_no_header_returns_none(self):
        from api.dependencies import get_optional_user

        result = await get_optional_user(auth_user=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_valid_token_returns_user_id(self):
        from api.dependencies import get_optional_user

        result = await get_optional_user(auth_user={"id": "user-uuid-123"})
        assert result == "user-uuid-123"

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        from api.dependencies import get_optional_user

        result = await get_optional_user(auth_user=None)
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_token_returns_none(self):
        """Optional auth must return None for expired/invalid tokens."""
        from api.dependencies import get_optional_user

        result = await get_optional_user(auth_user=None)
        assert result is None


class TestGuestReadOnlyGuard:
    @pytest.mark.asyncio
    async def test_guest_mutation_blocked_when_flag_enabled(self):
        import api.dependencies as dep_module

        original_flag = dep_module.GUEST_READ_ONLY_MODE
        dep_module.GUEST_READ_ONLY_MODE = True
        try:
            request = Request({"type": "http", "method": "POST", "headers": []})
            with pytest.raises(HTTPException) as exc_info:
                await dep_module.enforce_guest_read_only(request, auth_user={"id": "u1", "is_anonymous": True})
            assert exc_info.value.status_code == 403
        finally:
            dep_module.GUEST_READ_ONLY_MODE = original_flag

    @pytest.mark.asyncio
    async def test_guest_read_allowed_when_flag_enabled(self):
        import api.dependencies as dep_module

        original_flag = dep_module.GUEST_READ_ONLY_MODE
        dep_module.GUEST_READ_ONLY_MODE = True
        try:
            request = Request({"type": "http", "method": "GET", "headers": []})
            await dep_module.enforce_guest_read_only(request, auth_user={"id": "u1", "is_anonymous": True})
        finally:
            dep_module.GUEST_READ_ONLY_MODE = original_flag

    @pytest.mark.asyncio
    async def test_guest_write_allowed_when_flag_disabled(self):
        import api.dependencies as dep_module

        original_flag = dep_module.GUEST_READ_ONLY_MODE
        dep_module.GUEST_READ_ONLY_MODE = False
        try:
            request = Request({"type": "http", "method": "POST", "headers": []})
            await dep_module.enforce_guest_read_only(request, auth_user={"id": "u1", "is_anonymous": True})
        finally:
            dep_module.GUEST_READ_ONLY_MODE = original_flag

