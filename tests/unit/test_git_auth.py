from __future__ import annotations

from app.utils import git_auth


def test_get_git_auth_token_prefers_env(monkeypatch) -> None:
    git_auth._read_token_from_dotenv.cache_clear()
    monkeypatch.setenv("GIT_AUTH_TOKEN", "env-token-123")
    assert git_auth.get_git_auth_token() == "env-token-123"


def test_read_token_from_dotenv(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GIT_AUTH_TOKEN=dotenv-token-xyz\n", encoding="utf-8")
    assert git_auth._read_token_from_env_file(env_file) == "dotenv-token-xyz"
