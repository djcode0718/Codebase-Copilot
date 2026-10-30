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


def test_valid_citations_with_line_numbers(tmp_path):
    """Valid citations with existing files and valid line ranges pass validation."""
    from app.services.qa_service import validate_citations, validate_citation_details

    # Create a 50-line file
    test_file = tmp_path / "service.py"
    test_file.write_text("\n".join([f"line_{i}" for i in range(1, 51)]))

    retrieved = {"service.py"}
    text = "Refer to `service.py:10-25` and service.py:30 for implementation details."

    invalid = validate_citations(text, retrieved, str(tmp_path))
    assert invalid == []

    details = validate_citation_details(text, retrieved, str(tmp_path))
    assert len(details["valid"]) >= 1
    assert details["invalid_files"] == []
    assert details["fabricated_lines"] == []


def test_invalid_filenames_detected(tmp_path):
    """Non-existent or hallucinated filenames are flagged as invalid."""
    from app.services.qa_service import validate_citations, validate_citation_details

    retrieved = {"real_file.py"}
    text = "The code is in phantom_service.py and ghost_handler.ts."

    invalid = validate_citations(text, retrieved, str(tmp_path))
    assert sorted(invalid) == ["ghost_handler.ts", "phantom_service.py"]

    details = validate_citation_details(text, retrieved, str(tmp_path))
    assert "phantom_service.py" in details["invalid_files"]
    assert "ghost_handler.ts" in details["invalid_files"]


def test_fabricated_line_numbers_detected(tmp_path):
    """Line numbers exceeding physical file length are flagged as fabricated."""
    from app.services.qa_service import validate_citations, validate_citation_details

    # Create file with 20 lines
    test_file = tmp_path / "short_script.py"
    test_file.write_text("\n".join([f"print({i})" for i in range(20)]))

    retrieved = {"short_script.py"}
    # Line 999 exceeds 20 lines
    text = "Check `short_script.py:999` for the entry point."

    invalid = validate_citations(text, retrieved, str(tmp_path))
    assert "short_script.py:999" in invalid

    details = validate_citation_details(text, retrieved, str(tmp_path))
    assert len(details["fabricated_lines"]) == 1
    assert details["fabricated_lines"][0]["path"] == "short_script.py"
    assert details["fabricated_lines"][0]["line"] == 999


def test_mixed_valid_and_invalid_citations(tmp_path):
    """Mixed text containing valid files, invalid files, and fabricated lines is partitioned correctly."""
    from app.services.qa_service import validate_citations, validate_citation_details

    (tmp_path / "valid_a.py").write_text("\n".join([f"x = {i}" for i in range(100)]))
    (tmp_path / "valid_b.py").write_text("x = 1\n")  # 1 line

    retrieved = {"valid_a.py", "valid_b.py"}
    text = (
        "Look at valid_a.py:15-30 (valid), valid_b.py:500 (fabricated line), "
        "and imaginary_helper.py (hallucinated file)."
    )

    invalid = validate_citations(text, retrieved, str(tmp_path))
    assert "imaginary_helper.py" in invalid
    assert "valid_b.py:500" in invalid
    assert "valid_a.py:15" not in invalid
    assert "valid_a.py" not in invalid


def test_citations_outside_retrieved_context(tmp_path):
    """Citations that exist in repo but were outside retrieved context are tracked but not flagged as hallucinated."""
    from app.services.qa_service import validate_citation_details

    (tmp_path / "in_ctx.py").write_text("print('context')")
    (tmp_path / "outside_ctx.py").write_text("print('repo only')")

    retrieved = {"in_ctx.py"}  # outside_ctx is NOT retrieved
    text = "See in_ctx.py and outside_ctx.py."

    details = validate_citation_details(text, retrieved, str(tmp_path))
    assert "outside_ctx.py" in details["outside_context"]
    assert details["invalid_files"] == []  # Not a nonexistent hallucination


def test_sanitize_citations_preserves_valid_and_neutralizes_invalid(tmp_path):
    """Sanitizer preserves valid citations and line references, strips fabricated lines, and omits invalid files."""
    from app.services.qa_service import sanitize_citations

    (tmp_path / "core.py").write_text("\n".join([f"# line {i}" for i in range(50)]))

    retrieved = {"core.py"}
    text = "Review core.py:10-20 for logic, fake_lib.py for helpers, and core.py:9999 for cleanup."

    sanitized = sanitize_citations(text, retrieved, str(tmp_path))

    # Valid citation with lines is preserved
    assert "core.py:10-20" in sanitized
    # Fake file is neutralized
    assert "fake_lib.py" not in sanitized
    # Fabricated line on valid file is stripped to valid file reference
    assert "core.py:9999" not in sanitized
    assert "core.py" in sanitized

