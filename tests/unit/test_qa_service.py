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

