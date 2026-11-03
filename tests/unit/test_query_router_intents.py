import pytest
from unittest.mock import patch, MagicMock

from app.retrieval.query_router import (
    detect_excluded_folder,
    detect_aggregation,
    has_superlative,
    match_adjective_action,
    check_superlative_intent,
    LOW_CONFIDENCE_SIMILARITY_THRESHOLD
)


def test_detect_excluded_folder():
    # 1. Matching case
    assert detect_excluded_folder("what is inside node_modules/lodash?") == "node_modules"
    assert detect_excluded_folder("check venv files") == "venv"
    assert detect_excluded_folder("build/output.js path") == "build"
    
    # 2. Non-matching case
    assert detect_excluded_folder("how many files in src/api?") is None
    assert detect_excluded_folder("what is the main entry point") is None


def test_detect_aggregation():
    # 1. Matching cases
    assert detect_aggregation("how many tests do we have") is True
    assert detect_aggregation("total number of files") is True
    assert detect_aggregation("give me count of controllers") is True
    assert detect_aggregation("list all endpoints in router") is True
    
    # 2. Non-matching cases
    assert detect_aggregation("what does this function do") is False
    assert detect_aggregation("explain main.py architecture") is False


def test_has_superlative():
    # 1. Matching cases
    assert has_superlative("who is the most active user") is True
    assert has_superlative("least tested file") is True
    assert has_superlative("find the best approach") is True
    assert has_superlative("what is the messiest function") is True
    assert has_superlative("riskiest code blocks") is True
    
    # 2. Non-matching cases
    assert has_superlative("average complexity of code") is False
    assert has_superlative("how to clean up tech debt") is False


def test_match_adjective_action():
    # Adjective mapping matches
    assert match_adjective_action("most vulnerable component") == "security_review"
    assert match_adjective_action("riskiest tech debt") == "tech_debt_scan"
    assert match_adjective_action("least tested route") == "test_intelligence"
    assert match_adjective_action("highly coupled files") == "dependency_graph"
    
    # No match
    assert match_adjective_action("most complex logic") == "tech_debt_scan"  # matches "complex" -> tech_debt_scan
    assert match_adjective_action("cleanest code") is None


def test_check_superlative_intent_adjective_path():
    # Deterministic mapping paths (should not trigger LLM call)
    with patch("app.retrieval.query_router.classify_superlative_with_llm") as mock_llm:
        res = check_superlative_intent("tell me the most vulnerable file")
        assert res is not None
        assert res["suggested_action"] == "security_review"
        assert "Security Review" in res["message"]
        mock_llm.assert_not_called()


def test_check_superlative_intent_llm_fallback_path():
    # Fallback path (should trigger LLM call when has_superlative is True but adjective map fails)
    from app.retrieval.query_router import _superlative_cache
    _superlative_cache.cache.clear()
    with patch("app.retrieval.query_router.classify_superlative_with_llm", return_value="security_review") as mock_llm:
        res = check_superlative_intent("who is the best coder here")
        assert res is not None
        assert res["suggested_action"] == "security_review"
        mock_llm.assert_called_once_with("who is the best coder here")

    # LLM fallback fails or returns None -> check_superlative_intent should return None
    _superlative_cache.cache.clear()
    with patch("app.retrieval.query_router.classify_superlative_with_llm", return_value=None) as mock_llm:
        res = check_superlative_intent("who is the best coder here")
        assert res is None


def test_check_superlative_intent_cache():
    # Cache should prevent second LLM call for identical queries
    from app.retrieval.query_router import _superlative_cache
    _superlative_cache.cache.clear()  # clear cache first

    with patch("app.retrieval.query_router.classify_superlative_with_llm", return_value="security_review") as mock_llm:
        res1 = check_superlative_intent("who is the best developer here", index_name="test_index")
        assert res1 is not None
        assert res1["suggested_action"] == "security_review"
        mock_llm.assert_called_once()
        
        # Second call with same normalized query should hit cache
        mock_llm.reset_mock()
        res2 = check_superlative_intent("Who is the best developer here!", index_name="test_index")
        assert res2 is not None
        assert res2["suggested_action"] == "security_review"
        mock_llm.assert_not_called()


def test_threshold_value():
    assert LOW_CONFIDENCE_SIMILARITY_THRESHOLD == 0.40


def test_is_real_identifier():
    import tempfile
    import os
    import json
    from unittest.mock import patch
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        index_dir = os.path.join(tmp_dir, "index")
        os.makedirs(index_dir)
        
        index_name = "test_repo"
        repo_index_dir = os.path.join(index_dir, index_name)
        os.makedirs(repo_index_dir)
        
        # We put a specific key 'USE_RERANKER_TIMEOUT' to test exact matches
        graph_data = {
            "my_function": ["app.py:my_function"],
            "MyClass": ["app.py:MyClass"],
            "USE_RERANKER_TIMEOUT": []
        }
        with open(os.path.join(repo_index_dir, "relationship_graph.json"), "w", encoding="utf-8") as f:
            json.dump(graph_data, f)
            
        with patch("app.config.INDEX_DIR", index_dir):
            from app.retrieval.query_router import is_real_identifier, _identifier_cache
            
            # Clear cache first
            _identifier_cache.cache.clear()
            
            # Real function (exact match)
            assert is_real_identifier("my_function", index_name) is True
            # Real class (exact case-insensitive match)
            assert is_real_identifier("myclass", index_name) is True
            
            # Substring target that is a prefix should NOT match (e.g. USE_RERANKER vs USE_RERANKER_TIMEOUT)
            assert is_real_identifier("USE_RERANKER", index_name) is False
            
            # Substring target that is a suffix should NOT match (e.g. TIMEOUT vs USE_RERANKER_TIMEOUT)
            assert is_real_identifier("TIMEOUT", index_name) is False
            
            # Exact match of USE_RERANKER_TIMEOUT should match
            assert is_real_identifier("use_reranker_timeout", index_name) is True
            
            # Cache test: verify cache gets populated
            cache_key = (index_name, "my_function")
            assert _identifier_cache.get(cache_key) is True


@patch("app.services.qa_service.Settings")
@patch("app.services.qa_service._build_code_lookup_engine")
@patch("app.retrieval.query_router.is_real_identifier")
def test_relationship_query_clarification_flow(mock_is_real, mock_build_engine, mock_settings):
    from app.services.qa_service import handle_user_query
    from app.retrieval.query_router import QueryMode
    
    chat_engine = MagicMock()
    memory = MagicMock()
    
    # 1. Real identifier -> should proceed to retrieval (calls LLM complete)
    mock_is_real.return_value = True
    mock_settings.llm.complete.return_value = "Here are the calls..."
    
    # "What functions call handle_user_query" is recognized as RELATIONSHIP query mode
    res, _, _, mode = handle_user_query(
        "What functions call handle_user_query?",
        "test_index",
        chat_engine,
        memory
    )
    assert mode == QueryMode.RELATIONSHIP
    assert res == "Here are the calls..."
    mock_settings.llm.complete.assert_called_once()
    
    # 2. Vague identifier -> should ask for clarification
    mock_is_real.return_value = False
    mock_settings.llm.complete.reset_mock()
    
    res, _, _, mode = handle_user_query(
        "what functions call things?",
        "test_index",
        chat_engine,
        memory
    )
    assert mode == QueryMode.RELATIONSHIP
    assert "Could you point me to a specific file" in res
    mock_settings.llm.complete.assert_not_called()


@patch("app.retrieval.query_router.is_real_identifier")
@patch("api.services.chat_service._load_indexes")
@patch("api.services.chat_service._get_or_create_memory")
@patch("api.services.chat_service._resolve_query_mode")
@patch("app.retrieval.query_router.extract_relationship_target")
@pytest.mark.asyncio
async def test_stream_chat_relationship_clarification_flow(
    mock_extract_target,
    mock_resolve_mode,
    mock_get_memory,
    mock_load_indexes,
    mock_is_real
):
    from api.services.chat_service import _prepare_stream_prompt, QueryMode
    
    mock_load_indexes.return_value = (MagicMock(), MagicMock())
    memory = MagicMock()
    mock_get_memory.return_value = memory
    
    # Mock query mode resolution to RELATIONSHIP
    mock_resolve_mode.return_value = ("what calls handle_user_query", QueryMode.RELATIONSHIP)
    mock_extract_target.return_value = "handle_user_query"
    
    # Case A: target is real identifier -> should proceed to prompt creation without early response
    mock_is_real.return_value = True
    
    with patch("app.config.INDEX_DIR", "mock_index_dir"), \
         patch("app.llm.prompts.RELATIONSHIP_PROMPT", "Target: {target_symbol}, Refs: {references_list}"):
         
        res = await _prepare_stream_prompt(
            query="what calls handle_user_query",
            index_name="test_index",
            repo_id="test_repo",
            chat_id="test_chat",
            memory_context=None
        )
        
        assert "early_response" not in res
        assert res["query_mode"] == QueryMode.RELATIONSHIP
        assert "handle_user_query" in res["full_prompt"]

    # Case B: target is NOT real -> should return early with clarification response
    mock_is_real.return_value = False
    
    res_err = await _prepare_stream_prompt(
        query="what calls things",
        index_name="test_index",
        repo_id="test_repo",
        chat_id="test_chat",
        memory_context=None
    )
    assert "early_response" in res_err
    assert "Could you point me to a specific file" in res_err["early_response"]


def test_vague_queries_classified_as_architectural():
    """Verify that vague/broad exploration queries are classified as ARCHITECTURAL instead of strict CODE_LOOKUP."""
    from app.retrieval.query_router import classify_query, QueryMode

    with patch("app.retrieval.query_router._get_router_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "ARCHITECTURAL"
        mock_get_llm.return_value = mock_llm

        vague_queries = [
            "security",
            "how does it work?",
            "what is this?",
            "explain",
            "how does it work",
            "what is this",
            "explain this",
        ]

        for q in vague_queries:
            mode = classify_query(q)
            assert mode == QueryMode.ARCHITECTURAL, f"Query '{q}' should be classified as ARCHITECTURAL, got {mode}"


def test_vague_queries_with_resilient_llm_classifier():
    """Verify that ambiguous queries query the resilient LLM classifier and map response appropriately."""
    from app.retrieval.query_router import classify_query, QueryMode

    with patch("app.retrieval.query_router._get_router_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.complete.return_value = "ARCHITECTURAL"
        mock_get_llm.return_value = mock_llm

        # Ambiguous query that reaches Stage 2
        mode = classify_query("Can you tell me about the big picture here?")
        assert mode == QueryMode.ARCHITECTURAL
        mock_llm.complete.assert_called_once()


def test_specific_code_queries_remain_code_lookup():
    """Specific function/class/file queries must remain strict CODE_LOOKUP."""
    from app.retrieval.query_router import classify_query, QueryMode

    specific_queries = [
        "where is parse_documents function defined?",
        "show me the implementation of load_repository in file repo_loader.py",
        "what parameters does build_vector_index take?",
    ]

    for q in specific_queries:
        mode = classify_query(q)
        assert mode == QueryMode.CODE_LOOKUP, f"Specific query '{q}' should be CODE_LOOKUP, got {mode}"


# ─── Precheck Decoupling & Single Classification Tests (Phase 1B) ────────────

from app.retrieval.query_router import run_query_prechecks, PrecheckResult, GREETING_RESPONSE, QueryMode


def test_run_query_prechecks_greeting():
    res = run_query_prechecks("hello there", "test_idx")
    assert res.handled is True
    assert res.is_greeting is True
    assert res.response_text == GREETING_RESPONSE
    assert res.query_mode == QueryMode.CODE_LOOKUP


def test_run_query_prechecks_excluded_folder():
    res = run_query_prechecks("tell me about node_modules/react", "test_idx")
    assert res.handled is True
    assert res.is_excluded_folder is True
    assert "excluded from indexing" in res.response_text


def test_run_query_prechecks_aggregation():
    with patch("app.services.repo_stats_service.handle_aggregation_query", return_value="Total files: 42"):
        res = run_query_prechecks("how many files are there", "test_idx")
        assert res.handled is True
        assert res.is_aggregation is True
        assert res.response_text == "Total files: 42"


def test_run_query_prechecks_superlative():
    res = run_query_prechecks("most vulnerable file in repo", "test_idx")
    assert res.handled is True
    assert res.is_superlative is True
    assert res.action_suggestion is not None
    assert res.action_suggestion["suggested_action"] == "security_review"


def test_run_query_prechecks_pass_through():
    res = run_query_prechecks("how does auth work?", "test_idx")
    assert res.handled is False
    assert res.response_text is None


def test_run_query_prechecks_cta_followup_bypass():
    res = run_query_prechecks("hello", "test_idx", is_cta_followup=True)
    assert res.handled is False


def test_single_classification_pre_resolved_mode_orchestrator():
    """Verify that passing pre-resolved query_mode and resolved_query to orchestrate() skips re-classification."""
    from app.retrieval.orchestrator import SharedRetrievalOrchestrator, RetrievalTier
    from unittest.mock import MagicMock

    orch = SharedRetrievalOrchestrator()
    mock_vector_index = MagicMock()
    mock_vector_index.retrieve.return_value = []

    with patch("app.retrieval.orchestrator.classify_query") as mock_classify, \
         patch("app.retrieval.repository_isolation.enforce_chunk_isolation", side_effect=lambda nodes, **kwargs: nodes), \
         patch("app.retrieval.repository_isolation.resolve_repository_id", return_value="mock_repo"):

        decision = orch.orchestrate(
            query="how does payment work?",
            index_name="test_index",
            vector_index=mock_vector_index,
            query_mode=QueryMode.ARCHITECTURAL,
            resolved_query="how does payment work?",
            target_repo_id="mock_repo",
        )

        # classify_query MUST NOT be called because query_mode was provided!
        mock_classify.assert_not_called()
        assert decision.query_mode == QueryMode.ARCHITECTURAL


