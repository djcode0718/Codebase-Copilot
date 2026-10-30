from __future__ import annotations

from api.services import auth_service
from api.dependencies import get_current_user
from api.routers import auth


def test_logout_audit_requires_authenticated_user_dependency():
    route = next(r for r in auth.router.routes if getattr(r, "path", "") == "/logout/audit")
    dependency_calls = [dep.call for dep in route.dependant.dependencies]
    assert get_current_user in dependency_calls


def test_password_reset_complete_requires_authenticated_user_dependency():
    route = next(r for r in auth.router.routes if getattr(r, "path", "") == "/password-reset/audit-complete")
    dependency_calls = [dep.call for dep in route.dependant.dependencies]
    assert get_current_user in dependency_calls


def test_public_auth_endpoints_do_not_require_authenticated_user_dependency():
    public_paths = [
        "/register/preflight",
        "/login/preflight",
        "/login/audit",
        "/password-reset/audit-request",
    ]
    for path in public_paths:
        route = next(r for r in auth.router.routes if getattr(r, "path", "") == path)
        dependency_calls = [dep.call for dep in route.dependant.dependencies]
        assert get_current_user not in dependency_calls, f"Expected {path} to not require get_current_user"



def test_register_preflight_allows_new_email(client, monkeypatch):
    monkeypatch.setattr(auth_service, "normalize_email", lambda value: value.strip().lower())
    monkeypatch.setattr(auth_service, "validate_password", lambda value: None)
    monkeypatch.setattr(auth_service, "find_auth_user_by_email", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_service, "record_audit_log", lambda *_args, **_kwargs: None)

    res = client.post("/api/auth/register/preflight", json={"email": "new@example.com", "password": "StrongPass#123"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["email"] == "new@example.com"


def test_register_preflight_blocks_duplicate_email(client, monkeypatch):
    monkeypatch.setattr(auth_service, "normalize_email", lambda value: value.strip().lower())
    monkeypatch.setattr(auth_service, "validate_password", lambda value: None)
    monkeypatch.setattr(
        auth_service,
        "find_auth_user_by_email",
        lambda *_args, **_kwargs: {"id": "u-1", "email": "dup@example.com", "identities": [{"provider": "github"}]},
    )
    monkeypatch.setattr(auth_service, "list_identity_providers", lambda *_args, **_kwargs: ["github"])
    monkeypatch.setattr(auth_service, "record_identity_links_for_user", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_service, "record_audit_log", lambda *_args, **_kwargs: None)

    res = client.post("/api/auth/register/preflight", json={"email": "dup@example.com", "password": "StrongPass#123"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is False
    assert payload["providers"] == ["github"]


def test_login_preflight_surfaces_known_error_messages(client, monkeypatch):
    monkeypatch.setattr(auth_service, "normalize_email", lambda value: value.strip().lower())
    monkeypatch.setattr(
        auth_service,
        "evaluate_login_preflight",
        lambda *_args, **_kwargs: {
            "ok": False,
            "message": "No account was found for this email address.",
            "providers": [],
            "locked_until": None,
        },
    )
    monkeypatch.setattr(auth_service, "record_audit_log", lambda *_args, **_kwargs: None)

    res = client.post("/api/auth/login/preflight", json={"email": "ghost@example.com"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is False
    assert "No account" in payload["message"]


def test_login_audit_records_failure(client, monkeypatch):
    monkeypatch.setattr(auth_service, "normalize_email", lambda value: value.strip().lower())
    monkeypatch.setattr(auth_service, "evaluate_login_preflight", lambda *_args, **_kwargs: {"user_id": "u-1", "ok": True})
    monkeypatch.setattr(auth_service, "register_login_failure", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_service, "record_login_history", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_service, "record_audit_log", lambda *_args, **_kwargs: None)

    res = client.post(
        "/api/auth/login/audit",
        json={
            "email": "user@example.com",
            "success": False,
            "provider": "password",
            "failure_reason": "incorrect_password",
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_sessions_endpoint_returns_recent_history(client, monkeypatch):
    monkeypatch.setattr(
        auth_service,
        "get_recent_sessions",
        lambda *_args, **_kwargs: [
            {
                "id": "s-1",
                "provider": "password",
                "success": True,
                "login_at": "2026-08-07T00:00:00+00:00",
                "logout_at": None,
                "browser": "Chrome",
                "os": "Windows",
                "device": "Desktop",
                "ip_address": "127.0.0.1",
            }
        ],
    )

    res = client.get("/api/auth/sessions")
    assert res.status_code == 200
    payload = res.json()
    assert isinstance(payload["sessions"], list)
    assert payload["sessions"][0]["provider"] == "password"

