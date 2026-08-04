"""
tests/conftest.py
─────────────────
Shared pytest fixtures for the API test suite.

All fixtures use mocking so tests run without:
  - a real Supabase connection
  - a real LLM / Ollama
  - a real cloned repository on disk
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

# ── Ensure project root is importable ─────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Patch heavy startup deps BEFORE importing FastAPI app ─────────────────────
# These are module-level patches so the app never tries to connect to Groq/Ollama
os.environ.setdefault("LLM_PROVIDER", "groq")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-service-key")
os.environ.setdefault("OLLAMA_EMBED_MODEL", "nomic-embed-text")
os.environ.setdefault("USE_FAST_LLM", "false")
os.environ.setdefault("USE_COLBERT", "false")
os.environ.setdefault("INDEX_DIR", "/tmp/test_indices")
os.environ.setdefault("REPOS_DIR", "/tmp/test_repos")


def pytest_collection_modifyitems(config, items):
    for item in items:
        path_str = str(item.fspath).replace("\\", "/")

        if "/tests/integration/" in path_str:
            item.add_marker(pytest.mark.integration)
            continue

        if "/tests/unit/" in path_str:
            item.add_marker(pytest.mark.unit)
            continue

        # Default all remaining tests to unit unless explicitly marked otherwise.
        if "slow" not in item.keywords and "integration" not in item.keywords:
            item.add_marker(pytest.mark.unit)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def fake_user_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="session")
def fake_repo_id() -> str:
    return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@pytest.fixture(scope="session")
def fake_chat_id() -> str:
    return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


@pytest.fixture()
def fake_repo(fake_repo_id, fake_user_id):
    return {
        "id": fake_repo_id,
        "user_id": fake_user_id,
        "name": "test-repo",
        "source_url": "https://github.com/example/test-repo",
        "index_name": "test-repo",
        "status": "ready",
        "file_count": 42,
        "node_count": 300,
        "llm_provider": "groq",
        "created_at": "2025-01-01T00:00:00+00:00",
        "indexed_at": "2025-01-01T01:00:00+00:00",
    }


@pytest.fixture()
def fake_chat(fake_chat_id, fake_user_id, fake_repo_id):
    return {
        "id": fake_chat_id,
        "user_id": fake_user_id,
        "repo_id": fake_repo_id,
        "title": "What is the overall architecture?",
        "created_at": "2025-01-01T02:00:00+00:00",
        "updated_at": "2025-01-01T02:00:00+00:00",
    }


@pytest.fixture()
def fake_message(fake_chat_id):
    return {
        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
        "chat_id": fake_chat_id,
        "role": "user",
        "content": "What is the overall architecture?",
        "query_mode": None,
        "retrieved_files": None,
        "latency_ms": None,
        "created_at": "2025-01-01T02:00:00+00:00",
    }


@pytest.fixture()
def mock_supabase():
    """A fully mocked Supabase client."""
    mock = MagicMock()
    return mock


@pytest.fixture()
def auth_headers():
    """Fake Bearer token header (auth is mocked, value doesn't matter)."""
    return {"Authorization": "Bearer fake-valid-token"}


@pytest.fixture()
def client(fake_user_id, mock_supabase):
    """
    FastAPI TestClient with:
      - get_supabase() -> mock_supabase
      - get_current_user() -> fake_user_id
      - startup hook gracefully tolerates missing optional AI deps
    """
    from fastapi.testclient import TestClient
    from api.main import app
    from api.dependencies import get_supabase, get_current_user

    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    app.dependency_overrides[get_current_user] = lambda: fake_user_id

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
