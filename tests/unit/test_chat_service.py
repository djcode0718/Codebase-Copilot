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
from unittest.mock import AsyncMock, MagicMock, patch
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
_orig_modules = {m: sys.modules.get(m) for m in _STUBS}
_orig_query_mode = getattr(_orig_modules.get("app.retrieval.query_router"), "QueryMode", None)
for _m in _STUBS:
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
    RELATIONSHIP = "relationship"

sys.modules["app.retrieval.query_router"].QueryMode = _QueryMode


from api.services import chat_service  # noqa: E402

# Restore original modules to prevent pollution
for _m, _val in _orig_modules.items():
    if _val is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _val

from app.retrieval.query_router import QueryMode as _canonical_query_mode
chat_service.QueryMode = _canonical_query_mode
if "app.retrieval.query_router" in sys.modules:
    sys.modules["app.retrieval.query_router"].QueryMode = _canonical_query_mode


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


def test_ensure_llamaindex_forces_configure_settings():
    with patch.object(chat_service, "configure_llamaindex_settings") as cfg:
        chat_service._ensure_llamaindex()
    cfg.assert_called_once()


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
def test_redact_sensitive_text_for_log_masks_tokens_and_passwords():
    text = "Bearer abc123 token=xyz password=secret https://x-access-token:abc@github.com/org/repo"
    redacted = chat_service._redact_sensitive_text_for_log(text)
    assert "abc123" not in redacted
    assert "xyz" not in redacted
    assert "secret" not in redacted
    assert "x-access-token" in redacted
    assert "***" in redacted


def test_query_fingerprint_for_log_does_not_include_raw_query():
    query = "my token is super-secret"
    fp = chat_service._query_fingerprint_for_log(query)
    assert "super-secret" not in fp
    assert "len=" in fp
    assert "sha1=" in fp


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


@pytest.mark.asyncio
async def test_recover_from_stream_failure_uses_non_stream_generation_when_available():
    fallback_mod = MagicMock(generate_with_fallback=AsyncMock(return_value=" recovered answer "))
    with patch.dict(sys.modules, {"app.services.llm_fallback": fallback_mod}):
        text, path = await chat_service._recover_from_stream_failure("prompt", Exception("stream fail"))
    assert text == "recovered answer"
    assert path == "non_stream_recovery"


@pytest.mark.asyncio
async def test_recover_from_stream_failure_falls_back_to_safe_message_on_error():
    fallback_mod = MagicMock(
        generate_with_fallback=AsyncMock(side_effect=RuntimeError("boom")),
        get_resilient_llm=MagicMock(side_effect=RuntimeError("sync boom")),
    )
    with patch.dict(sys.modules, {"app.services.llm_fallback": fallback_mod}), \
         patch.object(chat_service, "_first_token_fallback_response", return_value="safe fallback"):
        text, path = await chat_service._recover_from_stream_failure("prompt", Exception("stream fail"))
    assert text == "safe fallback"
    assert path == "safe_fallback"


@pytest.mark.asyncio
async def test_recover_from_stream_failure_uses_sync_complete_when_async_recovery_fails():
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "sync recovered answer"
    fallback_mod = MagicMock(
        generate_with_fallback=AsyncMock(side_effect=RuntimeError("async fail")),
        get_resilient_llm=MagicMock(return_value=mock_llm),
    )
    with patch.dict(sys.modules, {"app.services.llm_fallback": fallback_mod}):
        text, path = await chat_service._recover_from_stream_failure("prompt", Exception("stream fail"))

    assert text == "sync recovered answer"
    assert path == "non_stream_recovery"
    mock_llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_stream_delta_accumulation_prevents_duplication():
    # Simulate a stream that yields:
    # 1. Chunk with delta="Hello"
    # 2. Chunk with delta=" world"
    # 3. Chunk with text="Hello world!" (cumulative, but delta field missing/empty)
    chunk1 = {"delta": "Hello", "text": None}
    chunk2 = {"delta": " world", "text": None}
    chunk3 = {"delta": None, "text": "Hello world!"}

    async def mock_stream_with_fallback(_prompt, **kwargs):
        yield chunk1
        yield chunk2
        yield chunk3

    fallback_mod = MagicMock(stream_with_fallback=mock_stream_with_fallback)
    with patch.dict(sys.modules, {"app.services.llm_fallback": fallback_mod}):
        tokens = []
        async for token in chat_service._stream_llm_response("test prompt"):
            tokens.append(token)

    # If duplication prevention works, the cumulative text chunk (chunk3)
    # should only yield the new delta part "!" instead of the full "Hello world!".
    assert tokens == ["Hello", " world", "!"]


@pytest.mark.asyncio
async def test_stream_chat_response_early_done_and_decoupled_suggestions():
    # Mock prepare stream prompt
    prep_mock = {
        "memory": MagicMock(),
        "resolved_query": "resolved query",
        "query_mode": chat_service.QueryMode.RELATIONSHIP,
        "reranked_nodes": [],
        "retrieved_files": [],
        "t_retrieval_ms": 10,
        "full_prompt": "full prompt",
    }

    async def mock_prepare(*args, **kwargs):
        return prep_mock

    # Mock streaming from LLM
    async def mock_stream_llm(*args, **kwargs):
        yield "Hello"
        yield " World"

    # Mock followup suggestions
    async def mock_followup(*args, **kwargs):
        return ["suggestion 1", "suggestion 2"]

    with patch("api.services.chat_service._prepare_stream_prompt", side_effect=mock_prepare), \
         patch("api.services.chat_service._stream_llm_response_with_guard", side_effect=mock_stream_llm), \
         patch("api.services.chat_service._persist_memory_turn") as mock_persist, \
         patch("api.services.chat_service._generate_followup_suggestions", side_effect=mock_followup) as mock_sugg, \
         patch("api.services.chat_service.is_general_knowledge_or_preference_query", return_value=False), \
         patch("app.services.qa_service.validate_citations", return_value=[]) as mock_citation:

        events = []
        async for sse_data in chat_service.stream_chat_response(
            query="Show me handle_user_query function",
            index_name="test_index",
            repo_id="test_repo",
            chat_id="test_chat",
        ):
            events.append(sse_data)

    import json
    parsed_events = []
    for evt in events:
        assert evt.startswith("data: ")
        assert evt.endswith("\n\n")
        payload = json.loads(evt[6:-2])
        parsed_events.append(payload)

    # Verify event types in order:
    assert parsed_events[0] == {"type": "token", "content": "Hello World"}
    assert parsed_events[1]["type"] == "metadata"
    assert parsed_events[2] == {"type": "done"}
    assert parsed_events[3] == {"type": "followup_pending"}
    assert parsed_events[4] == {"type": "followup_suggestions", "questions": ["suggestion 1", "suggestion 2"]}

    # Verify passive citation validation was called
    mock_citation.assert_called_once()


@pytest.mark.asyncio
async def test_prepare_stream_prompt_passes_target_repo_id_to_orchestrator():
    """Verify _prepare_stream_prompt propagates repo_id as target_repo_id to orchestrator."""
    from app.retrieval.orchestrator import RetrievalDecision, RetrievalTier
    from app.retrieval.query_router import QueryMode

    repo_uuid = "verified-repo-uuid-555"
    idx_name = "test_index"

    mock_decision = RetrievalDecision(
        query="test query",
        resolved_query="test query",
        query_mode=QueryMode.CODE_LOOKUP,
        selected_tier=RetrievalTier.TIER3_HYBRID_CODE,
        nodes=[],
        retrieved_files=[],
        confidence_score=0.9,
        should_abstain=False,
    )

    mock_orch = MagicMock()
    mock_orch.orchestrate.return_value = mock_decision

    with patch("api.services.chat_service._stream_prechecks", return_value=None), \
         patch("api.services.chat_service._load_indexes", AsyncMock(return_value=(MagicMock(), MagicMock()))), \
         patch("app.retrieval.orchestrator.get_retrieval_orchestrator", return_value=mock_orch), \
         patch("api.services.chat_service._build_full_prompt", return_value="assembled prompt"):

        res = await chat_service._prepare_stream_prompt(
            query="test query",
            index_name=idx_name,
            repo_id=repo_uuid,
            chat_id="test_chat",
            memory_context=None,
        )

        mock_orch.orchestrate.assert_called_once()
        _, kwargs = mock_orch.orchestrate.call_args
        assert kwargs.get("target_repo_id") == repo_uuid




