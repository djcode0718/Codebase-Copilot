"""
Unit tests for api/services/chat_service.py

Tests cover:
- Session cache helpers (_get_or_init_session, _save_session)
- _is_no_match_code_lookup_response
- _looks_repository_intent (positive & negative)
- _should_force_no_match
- _repo_focused_rephrase_suggestions
- _build_fallback_llms provider priority ordering
- Negative paths: empty/None inputs
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock, patch
import pytest


# ─── Stub heavy dependencies before importing chat_service ──────────────────

_STUBS = [
    "llama_index",
    "llama_index.core",
    "llama_index.core.Settings",
    "llama_index.core.memory",
    "llama_index.core.memory.ChatMemoryBuffer",
    "llama_index.core.retrievers",
    "llama_index.core.retrievers.QueryFusionRetriever",
    "llama_index.llms.groq",
    "llama_index.llms.gemini",
    "llama_index.llms.ollama",
    "app.llm.llm_client",
    "app.retrieval.query_router",
    "app.retrieval.reranker",
    "app.services.qa_service",
]
for _m in _STUBS:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Ensure llama_index.core.Settings is a real-ish object so attribute access works.
settings_mock = MagicMock()
settings_mock.llm = None
settings_mock.embed_model = None
sys.modules["llama_index.core"].Settings = settings_mock

import enum as _enum

class _QueryMode(_enum.Enum):
    CODE_LOOKUP  = "code_lookup"
    ARCHITECTURAL = "architectural"

sys.modules["app.retrieval.query_router"].QueryMode = _QueryMode


from api.services import chat_service  # noqa: E402


# ─── Session cache helpers ────────────────────────────────────────────────────

def setup_function():
    """Clear session cache before each test."""
    chat_service._session_cache.clear()


def test_get_or_init_session_returns_none_triple_for_unknown():
    result = chat_service._get_or_init_session("repo-1", "chat-1")
    assert result == (None, None, None)


def test_save_and_get_session_roundtrip():
    engine = MagicMock()
    memory = MagicMock()
    chat_service._save_session("repo-1", "chat-2", engine, memory, "code_lookup")

    result = chat_service._get_or_init_session("repo-1", "chat-2")
    assert result == (engine, memory, "code_lookup")


def test_session_cache_isolated_per_key():
    eng_a = MagicMock()
    eng_b = MagicMock()
    chat_service._save_session("repo-A", "chat-1", eng_a, None, "code_lookup")
    chat_service._save_session("repo-B", "chat-1", eng_b, None, "architectural")

    assert chat_service._get_or_init_session("repo-A", "chat-1")[0] is eng_a
    assert chat_service._get_or_init_session("repo-B", "chat-1")[0] is eng_b
    assert chat_service._get_or_init_session("repo-C", "chat-1") == (None, None, None)


def test_save_session_overwrites_existing():
    engine_old = MagicMock()
    engine_new = MagicMock()
    chat_service._save_session("r", "c", engine_old, None, "code_lookup")
    chat_service._save_session("r", "c", engine_new, None, "architectural")

    result = chat_service._get_or_init_session("r", "c")
    assert result[0] is engine_new
    assert result[2] == "architectural"


# ─── _is_no_match_code_lookup_response ───────────────────────────────────────

def test_is_no_match_response_matches_sentinel():
    sentinel = chat_service._NO_MATCH_CODE_LOOKUP_RESPONSE
    assert chat_service._is_no_match_code_lookup_response(sentinel) is True


def test_is_no_match_response_false_for_real_answer():
    assert chat_service._is_no_match_code_lookup_response("Here is the implementation:") is False


def test_is_no_match_response_false_for_empty():
    assert chat_service._is_no_match_code_lookup_response("") is False


def test_is_no_match_response_false_for_none():
    assert chat_service._is_no_match_code_lookup_response(None) is False


# ─── _looks_repository_intent ────────────────────────────────────────────────

@pytest.mark.parametrize("query", [
    "How does the repo work?",
    "Show me the main.py file",
    "What does the function do?",
    "List all API endpoints",
    "Show me app/services/chat_service.py",
    "Find the bug in this code",
])
def test_looks_repository_intent_true(query):
    assert chat_service._looks_repository_intent(query) is True


@pytest.mark.parametrize("query", [
    "What is the weather today?",
    "Tell me a joke",
    "Who is the president?",
    "",
])
def test_looks_repository_intent_false(query):
    assert chat_service._looks_repository_intent(query) is False


# ─── _should_force_no_match ──────────────────────────────────────────────────

def test_should_force_no_match_irrelevant_query_low_score():
    assert chat_service._should_force_no_match("Tell me a joke", 0.3) is True


def test_should_force_no_match_irrelevant_query_high_score():
    # High score overrides — don't force no-match even for off-topic query.
    assert chat_service._should_force_no_match("Tell me a joke", 0.8) is False


def test_should_force_no_match_repo_query_always_false():
    # Repo-intent queries should never be force-no-matched.
    assert chat_service._should_force_no_match("How does the API router work?", 0.1) is False


# ─── _repo_focused_rephrase_suggestions ──────────────────────────────────────

def test_rephrase_suggestions_returns_non_empty_list():
    suggestions = chat_service._repo_focused_rephrase_suggestions()
    assert isinstance(suggestions, list)
    assert len(suggestions) >= 1
    for s in suggestions:
        assert isinstance(s, str)
        assert s.strip()


# ─── _build_fallback_llms provider ordering ──────────────────────────────────

def test_build_fallback_llms_excludes_active_provider():
    """Active provider should not appear in the fallback list."""
    spec_groq = MagicMock(provider="groq", model_name="llama-3.1-8b-instant")
    spec_gemini = MagicMock(provider="gemini", model_name="models/gemini-flash-latest")
    spec_ollama = MagicMock(provider="ollama", model_name="llama3.2:3b")
    with patch.object(chat_service, "LLM_PROVIDER", "groq"), \
         patch("app.services.model_manager.get_available_model_specs", return_value=[spec_groq, spec_gemini, spec_ollama]), \
         patch("app.services.model_manager.create_llm_client", side_effect=lambda s: f"{s.provider}:{s.model_name}"):
        candidates = chat_service._build_fallback_llms()
        providers = [name for name, _ in candidates]
        assert "groq" not in providers
        assert providers == ["gemini", "ollama"]


def test_build_fallback_llms_returns_list():
    spec_gemini = MagicMock(provider="gemini", model_name="models/gemini-flash-latest")
    with patch.object(chat_service, "LLM_PROVIDER", "ollama"), \
         patch("app.services.model_manager.get_available_model_specs", return_value=[spec_gemini]), \
         patch("app.services.model_manager.create_llm_client", return_value="gemini-client"):
        candidates = chat_service._build_fallback_llms()
        assert isinstance(candidates, list)
        assert candidates == [("gemini", "gemini-client")]


@pytest.mark.asyncio
async def test_stream_guard_yields_tokens_when_first_token_arrives_in_time():
    async def fake_stream(_prompt):
        await asyncio.sleep(0.01)
        yield "hello"
        yield " world"

    with patch.object(chat_service, "_stream_llm_response", side_effect=fake_stream):
        chunks = []
        async for delta in chat_service._stream_llm_response_with_guard("prompt", timeout_seconds=0.2):
            chunks.append(delta)

    assert chunks == ["hello", " world"]


@pytest.mark.asyncio
async def test_stream_guard_raises_on_first_token_timeout():
    async def slow_stream(_prompt):
        await asyncio.sleep(0.2)
        yield "late"

    with patch.object(chat_service, "_stream_llm_response", side_effect=slow_stream):
        with pytest.raises(chat_service.StreamFirstTokenTimeoutError):
            async for _delta in chat_service._stream_llm_response_with_guard("prompt", timeout_seconds=0.01):
                pass
