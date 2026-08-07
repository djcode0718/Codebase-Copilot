from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

_ENV_TOKEN_KEYS = ("GIT_AUTH_TOKEN", "GITHUB_TOKEN", "GITHUB_ACCESS_TOKEN")


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _read_token_from_env_file(env_path: Path) -> str:
    if not env_path.exists():
        return ""
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in _ENV_TOKEN_KEYS:
                return _strip_quotes(value.strip())
    except Exception:
        return ""

    return ""


@lru_cache(maxsize=1)
def _read_token_from_dotenv() -> str:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    return _read_token_from_env_file(env_path)


def get_git_auth_token() -> Optional[str]:
    for key in _ENV_TOKEN_KEYS:
        value = (os.getenv(key) or "").strip()
        if value:
            return value

    token = _read_token_from_dotenv().strip()
    return token or None
