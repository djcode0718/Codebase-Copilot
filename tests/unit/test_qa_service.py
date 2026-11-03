import pytest
from unittest.mock import MagicMock, patch
from llama_index.core.schema import NodeWithScore, TextNode
from app.services.qa_service import handle_user_query


@patch("app.services.qa_service.Settings")
@patch("app.services.qa_service._build_code_lookup_engine")
@patch("app.services.qa_service.classify_query")
@patch("app.services.qa_service.rerank_with_cross_encoder")
def test_handle_user_query_respects_use_reranker(mock_rerank, mock_classify, mock_build_engine, mock_settings, tmp_path):
    from app.retrieval.query_router import QueryMode
    mock_classify.return_value = QueryMode.CODE_LOOKUP
    
    mock_engine = MagicMock()
    mock_engine._retriever.retrieve.return_value = [
        NodeWithScore(node=TextNode(text="code", metadata={"path": "valid.py"}), score=0.9)
    ]
    mock_build_engine.return_value = mock_engine
    
    # Mock LLM and validation
    mock_settings.llm = MagicMock()
    mock_settings.llm.complete.return_value = "Mock response"
    
    memory = MagicMock()
    
    # Scenario A: USE_RERANKER = True -> should call reranker
    with patch("app.config.USE_RERANKER", True), \
         patch("app.config.REPOS_DIR", str(tmp_path)), \
         patch("app.services.qa_service.validate_citations", return_value=[]):
        
        mock_rerank.return_value = [
            NodeWithScore(node=TextNode(text="code", metadata={"path": "valid.py"}), score=0.9)
        ]
        
        handle_user_query("query", "test_index", memory)
        mock_rerank.assert_called_once()
        
    mock_rerank.reset_mock()
    
    # Scenario B: USE_RERANKER = False -> should NOT call reranker
    with patch("app.config.USE_RERANKER", False), \
         patch("app.config.REPOS_DIR", str(tmp_path)), \
         patch("app.services.qa_service.validate_citations", return_value=[]):
        
        handle_user_query("query", "test_index", memory)
        mock_rerank.assert_not_called()


def test_qa_service_module_importable():
    import app.services.qa_service as m  # noqa: F401
    assert m is not None


def test_check_low_confidence_handles_rrf_scores():
    """Verify that RRF scores (~0.016-0.033) are recognized and not rejected as low confidence."""
    from app.services.qa_service import _check_low_confidence
    from app.retrieval.query_router import QueryMode

    # Node with typical RRF fusion score
    node = NodeWithScore(node=TextNode(text="def handle(): pass", metadata={"path": "handler.py"}), score=0.028)
    assert _check_low_confidence([node], "RRF-Test", query_mode=QueryMode.CODE_LOOKUP) is False


def test_check_low_confidence_architectural_mode_preserves_context():
    """Architectural mode queries reasoning over code chunks are never aborted by confidence check."""
    from app.services.qa_service import _check_low_confidence
    from app.retrieval.query_router import QueryMode

    node = NodeWithScore(node=TextNode(text="class Architecture: pass", metadata={"path": "arch.py"}), score=0.32)
    assert _check_low_confidence([node], "Arch-Test", query_mode=QueryMode.ARCHITECTURAL) is False


def test_check_low_confidence_empty_nodes_is_low_confidence():
    """Empty retrieval genuinely has no evidence and must trigger low confidence."""
    from app.services.qa_service import _check_low_confidence
    from app.retrieval.query_router import QueryMode

    assert _check_low_confidence([], "Empty-Test", query_mode=QueryMode.CODE_LOOKUP) is True


def test_answerable_question_reaches_generation(tmp_path):
    """Answerable query with retrieved context generates an answer instead of a canned refusal."""
    from app.services.qa_service import handle_user_query, _CLARIFICATION_RESPONSE
    from app.retrieval.query_router import QueryMode

    (tmp_path / "auth.py").write_text("def verify_jwt(): return True")

    mock_engine = MagicMock()
    # Return valid retrieved node with modest CrossEncoder score (0.35)
    mock_engine._retriever.retrieve.return_value = [
        NodeWithScore(node=TextNode(text="def verify_jwt(): return True", metadata={"path": "auth.py"}), score=0.35)
    ]

    with patch("app.services.qa_service.classify_query", return_value=QueryMode.CODE_LOOKUP), \
         patch("app.services.qa_service._build_code_lookup_engine", return_value=mock_engine), \
         patch("app.services.qa_service.rerank_with_cross_encoder", return_value=mock_engine._retriever.retrieve.return_value), \
         patch("app.services.qa_service.Settings") as mock_settings, \
         patch("app.config.USE_RERANKER", True), \
         patch("app.config.REPOS_DIR", str(tmp_path)), \
         patch("app.services.qa_service.validate_citations", return_value=[]):

        mock_llm = MagicMock()
        mock_llm.complete.return_value = "verify_jwt validates JSON web tokens in auth.py."
        mock_settings.llm = mock_llm

        memory = MagicMock()
        res, _, _, _ = handle_user_query("how does verify_jwt work?", "test_idx", memory)

        # Did NOT return canned refusal; generated the real answer!
        assert res != _CLARIFICATION_RESPONSE
        assert "verify_jwt" in res
        mock_llm.complete.assert_called_once()


def test_relationship_query_reads_graph_under_read_lock_and_releases_before_llm():
    """Verify that relationship graph lookup in QA is protected by acquire_index_read and released before LLM completion."""
    from app.services.qa_service import handle_user_query
    from app.retrieval.query_router import QueryMode
    from app.indexing.incremental import get_index_rwlock

    test_idx = "idx_rel_lock_test"
    lock = get_index_rwlock(test_idx)

    lock_active_during_graph_read = []
    lock_active_during_llm_complete = []

    def fake_get_refs(index_name, target):
        lock_active_during_graph_read.append(lock._active_readers)
        return ["core.py:42", "api.py:10"]

    def fake_llm_complete(prompt):
        lock_active_during_llm_complete.append(lock._active_readers)
        return "handle_user_query is called in core.py and api.py"

    with patch("app.services.qa_service._resolve_query_mode", return_value=("what calls handle_user_query", QueryMode.RELATIONSHIP)), \
         patch("app.retrieval.query_router.extract_relationship_target", return_value="handle_user_query"), \
         patch("app.retrieval.query_router.is_real_identifier", return_value=True), \
         patch("app.services.qa_service._get_relationship_refs", side_effect=fake_get_refs), \
         patch("app.services.qa_service.Settings") as mock_settings:

        mock_llm = MagicMock()
        mock_llm.complete.side_effect = fake_llm_complete
        mock_settings.llm = mock_llm

        memory = MagicMock()
        res, _, _, mode = handle_user_query("what calls handle_user_query", test_idx, memory)

        # 1. Graph lookup was executed under read lock (active_readers == 1)
        assert len(lock_active_during_graph_read) == 1
        assert lock_active_during_graph_read[0] == 1, f"Expected 1 active reader during graph read, got {lock_active_during_graph_read[0]}"

        # 2. Read lock was released BEFORE LLM completion (active_readers == 0)
        assert len(lock_active_during_llm_complete) == 1
        assert lock_active_during_llm_complete[0] == 0, f"Expected 0 active readers during LLM complete, got {lock_active_during_llm_complete[0]}"

        # 3. Overall lock is clean after call
        assert lock._active_readers == 0
        assert "core.py" in res or "handle_user_query" in res


def test_handle_user_query_propagates_target_repo_id():
    """Verify handle_user_query passes target_repo_id to SharedRetrievalOrchestrator."""
    from app.services.qa_service import handle_user_query
    from app.retrieval.orchestrator import RetrievalDecision, RetrievalTier
    from app.retrieval.query_router import QueryMode

    target_id = "test-target-repo-uuid-999"
    test_idx = "test_idx_propagation"

    mock_decision = RetrievalDecision(
        query="query",
        resolved_query="query",
        query_mode=QueryMode.CODE_LOOKUP,
        selected_tier=RetrievalTier.TIER3_HYBRID_CODE,
        nodes=[NodeWithScore(node=TextNode(text="code", metadata={"path": "test.py"}), score=0.9)],
        retrieved_files=["test.py"],
        confidence_score=0.9,
        should_abstain=False,
    )

    mock_engine = MagicMock()
    mock_engine._retriever.retrieve.return_value = mock_decision.nodes

    with patch("app.services.qa_service._run_pre_routing_checks", return_value=None), \
         patch("app.services.qa_service._resolve_query_mode", return_value=("query", QueryMode.CODE_LOOKUP)), \
         patch("app.services.qa_service._get_indexes", return_value=(MagicMock(), None)), \
         patch("app.services.qa_service._ensure_engine_for_mode", return_value=mock_engine), \
         patch("app.retrieval.orchestrator.get_retrieval_orchestrator") as mock_get_orch, \
         patch("app.services.qa_service._execute_cross_encoder_path", return_value="Executed path"), \
         patch("app.config.USE_RERANKER", True):

        mock_orch = MagicMock()
        mock_orch.orchestrate.return_value = mock_decision
        mock_get_orch.return_value = mock_orch

        memory = MagicMock()
        res, _, _, _ = handle_user_query(
            "where is config?",
            test_idx,
            memory=memory,
            target_repo_id=target_id,
        )

        mock_orch.orchestrate.assert_called_once()
        _, kwargs = mock_orch.orchestrate.call_args
        assert kwargs.get("target_repo_id") == target_id


def test_handle_user_query_fast_fails_on_target_repo_id_mismatch():
    """Verify handle_user_query abstains when target_repo_id does not match active index canonical ID."""
    from app.services.qa_service import handle_user_query
    from app.retrieval.query_router import QueryMode
    from app.retrieval.orchestrator import DEFAULT_ABSTENTION_MESSAGE

    # FedSegX has a known canonical ID in STATIC_REPO_ID_MAP: bc5f54ec-7113-4132-b39e-bd94a0d2726e
    # Passing an arbitrary mismatched UUID triggers strict isolation rejection
    mismatched_id = "00000000-0000-0000-0000-000000000000"
    fedsegx_index = "FedSegX"

    mock_engine = MagicMock()

    with patch("app.services.qa_service._run_pre_routing_checks", return_value=None), \
         patch("app.services.qa_service._resolve_query_mode", return_value=("how does FedSegX train?", QueryMode.CODE_LOOKUP)), \
         patch("app.services.qa_service._get_indexes", return_value=(MagicMock(), None)), \
         patch("app.services.qa_service._ensure_engine_for_mode", return_value=mock_engine), \
         patch("app.services.qa_service.Settings") as mock_settings:

        mock_llm = MagicMock()
        mock_settings.llm = mock_llm

        memory = MagicMock()
        res, _, _, _ = handle_user_query(
            "how does FedSegX train?",
            fedsegx_index,
            memory=memory,
            target_repo_id=mismatched_id,
        )

        # Must abstain immediately with default abstention message and never invoke LLM
        assert res == DEFAULT_ABSTENTION_MESSAGE or "does not contain sufficient evidence" in res
        mock_llm.complete.assert_not_called()




