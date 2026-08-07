from __future__ import annotations

import pytest

from api.services import auth_service


def test_normalize_email_trims_and_lowercases() -> None:
    assert auth_service.normalize_email('  USER@Example.COM  ') == 'user@example.com'


def test_normalize_email_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        auth_service.normalize_email('not-an-email')


def test_validate_password_length() -> None:
    with pytest.raises(ValueError):
        auth_service.validate_password('short')


def test_list_identity_providers_from_metadata() -> None:
    user_payload = {
        'app_metadata': {'provider': 'google'},
        'identities': [{'provider': 'github'}, {'provider': 'email'}],
    }
    assert auth_service.list_identity_providers(user_payload) == ['github', 'google', 'password']


def test_check_account_lock_from_future_timestamp() -> None:
    state = {'locked_until': '2099-01-01T00:00:00+00:00'}
    locked, locked_until = auth_service.check_account_lock(state)
    assert locked is True
    assert locked_until is not None


def test_missing_auth_table_name_detects_schema_cache_error() -> None:
    err = Exception("Could not find the table 'public.auth_audit_logs' in the schema cache (PGRST205)")
    assert auth_service._missing_auth_table_name(err) == 'auth_audit_logs'


def test_safe_insert_warns_once_for_missing_table(monkeypatch) -> None:
    class _BadInsertQuery:
        def insert(self, _payload):
            return self

        def execute(self):
            raise Exception("Could not find the table 'public.auth_audit_logs' in the schema cache")

    warnings: list[str] = []
    monkeypatch.setattr(auth_service.logger, 'warning', lambda msg: warnings.append(str(msg)))
    auth_service._MISSING_AUTH_TABLE_WARNED.clear()

    auth_service._safe_insert(_BadInsertQuery(), {'k': 'v'})
    auth_service._safe_insert(_BadInsertQuery(), {'k': 'v2'})

    assert len(warnings) == 1
    assert 'auth_audit_logs' in warnings[0]
