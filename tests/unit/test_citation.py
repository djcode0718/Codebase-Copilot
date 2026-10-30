import pytest
from unittest.mock import MagicMock, patch
from app.services.qa_service import extract_cited_files, validate_citations, handle_user_query
from llama_index.core.schema import NodeWithScore, TextNode


def test_extract_cited_files():
    text = "The entry points are app/main.py and api/main.py. Also check README.md and index.js."
    assert extract_cited_files(text) == {"app/main.py", "api/main.py", "README.md", "index.js"}
    
    text_with_brackets = "See [app/utils/logger.py] or `config.py` for details."
    assert extract_cited_files(text_with_brackets) == {"app/utils/logger.py", "config.py"}


def test_validate_citations(tmp_path):
    # Setup test workspace files
    (tmp_path / "valid.py").write_text("print('hello')")
    
    retrieved_paths = {"valid.py", "in_context.py"}
    
    # Test text containing:
    # 1. Valid physical file: "valid.py"
    # 2. In-context (retrieved) path: "in_context.py"
    # 3. Invalid (hallucinated) path: "fake_file.py"
    text = "Check valid.py, in_context.py, and fake_file.py."
    
    invalid = validate_citations(text, retrieved_paths, str(tmp_path))
    assert invalid == ["fake_file.py"]


@patch("app.services.qa_service.validate_citations")
@patch("app.services.qa_service.Settings")
@patch("app.services.qa_service._build_code_lookup_engine")
@patch("app.services.qa_service.classify_query")
@patch("app.services.qa_service.rerank_with_cross_encoder")
def test_retrieve_and_answer_strict_citation_mode(mock_rerank, mock_classify, mock_build_engine, mock_settings, mock_validate, tmp_path):
    from app.retrieval.query_router import QueryMode
    mock_classify.return_value = QueryMode.CODE_LOOKUP
    
    # Mock retrieve to return nodes
    mock_engine = MagicMock()
    mock_engine._retriever.retrieve.return_value = [
        NodeWithScore(node=TextNode(text="code", metadata={"path": "valid.py"}), score=0.9)
    ]
    mock_build_engine.return_value = mock_engine
    
    mock_rerank.return_value = [
        NodeWithScore(node=TextNode(text="code", metadata={"path": "valid.py"}), score=0.9)
    ]
    
    # Set citation validation mode to strict
    with patch("app.config.CITATION_VALIDATION_MODE", "strict"), \
         patch("app.config.USE_RERANKER", True), \
         patch("app.config.REPOS_DIR", str(tmp_path)):
        
        # 1. First completion returns hallucinated path
        # 2. Second completion returns clean path (resolved)
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = ["Check hallucinated.py", "Check valid.py"]
        mock_settings.llm = mock_llm
        
        # Mock validation:
        # First call: returns ["hallucinated.py"]
        # Second call: returns []
        mock_validate.side_effect = [["hallucinated.py"], []]
        
        memory = MagicMock()
        res, _, _, _ = handle_user_query("query", "test_index", memory)
        
        assert res == "Check valid.py"
        assert mock_llm.complete.call_count == 2
