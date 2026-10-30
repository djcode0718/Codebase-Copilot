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


