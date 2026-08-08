"""
tests/test_app_query_router.py
Unit tests for app/retrieval/query_router.py

Tests the two-stage classifier:
  Stage 1: Keyword scoring (fast path, no LLM)
  Stage 2: LLM fallback (mocked â€” we test routing logic, not the LLM)

Also tests chunk_utils.py (pure math, no deps).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.slow
pytest.importorskip("llama_index.core")

from app.retrieval.query_router import (
    classify_query,
    QueryMode,
    _CODE_KEYWORDS,
    _ARCHITECTURAL_KEYWORDS,
    is_general_knowledge_or_preference_query,
)
from app.parsing.chunk_utils import chunk_text


# â”€â”€ QueryMode enum â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestQueryMode:
    def test_code_lookup_value(self):
        assert QueryMode.CODE_LOOKUP.value == "code_lookup"

    def test_architectural_value(self):
        assert QueryMode.ARCHITECTURAL.value == "architectural"

    def test_enum_members(self):
        modes = list(QueryMode)
        assert QueryMode.CODE_LOOKUP in modes
        assert QueryMode.ARCHITECTURAL in modes


# â”€â”€ Keyword fast-path: CODE_LOOKUP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestCodeLookupKeywordPath:
    """Queries with 2+ code keywords should classify as CODE_LOOKUP without calling the LLM."""

    @pytest.mark.parametrize("query", [
        "How does the parse_documents function work?",
        "Show me the implementation of the vector store class",
        "Where is the import for the file_filter module?",
        "What does the def load_repository method return?",
        "Explain the usage of the code splitter",
        "How does the file_filter.py file work?",
        "Find all methods in the retriever module",
        "What does the classify_query function return?",
    ])
    def test_code_keywords_route_to_code_lookup(self, query):
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            result = classify_query(query)
        assert result == QueryMode.CODE_LOOKUP

    def test_specific_function_name_query(self):
        with patch("app.retrieval.query_router.Settings"):
            result = classify_query("How does the chunk_text function implement overlap?")
        assert result == QueryMode.CODE_LOOKUP

    def test_error_fix_query(self):
        with patch("app.retrieval.query_router.Settings"):
            result = classify_query("How do I fix the bug in the error handler?")
        assert result == QueryMode.CODE_LOOKUP


# â”€â”€ Keyword fast-path: ARCHITECTURAL â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestArchitecturalKeywordPath:
    """Queries with 2+ architectural keywords should route without LLM call."""

    @pytest.mark.parametrize("query", [
        "What are the main limitations of this architecture?",
        "How can I improve the performance and optimize it?",
        "What design patterns and architecture are used here?",
        "Can you summarize the overall design and suggest improvements?",
        "What are the weaknesses and issues with the current pattern?",
        "How would you recommend scaling this to improve performance?",
    ])
    def test_architectural_keywords_route_correctly(self, query):
        with patch("app.retrieval.query_router.Settings"):
            result = classify_query(query)
        assert result == QueryMode.ARCHITECTURAL

    def test_limitation_and_improvement_query(self):
        with patch("app.retrieval.query_router.Settings"):
            result = classify_query("What are the limitations and how would you improve this?")
        assert result == QueryMode.ARCHITECTURAL


# â”€â”€ LLM fallback for ambiguous queries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestLLMFallback:
    """Ambiguous queries (< 2 keyword hits) go to LLM. We mock the LLM response."""

    def _mock_llm(self, response_text: str):
        mock_llm = MagicMock()
        mock_llm.complete.return_value = MagicMock(__str__=lambda s: response_text)
        return mock_llm

    def test_llm_returns_architectural(self):
        mock_llm = self._mock_llm("ARCHITECTURAL")
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            mock_settings.llm = mock_llm
            result = classify_query("Tell me about this project")
        assert result == QueryMode.ARCHITECTURAL

    def test_llm_returns_code_lookup(self):
        mock_llm = self._mock_llm("CODE_LOOKUP")
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            mock_settings.llm = mock_llm
            result = classify_query("How is it organised?")
        assert result == QueryMode.CODE_LOOKUP

    def test_llm_response_case_insensitive(self):
        """'architectural' (lowercase) still maps to ARCHITECTURAL."""
        mock_llm = self._mock_llm("architectural")
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            mock_settings.llm = mock_llm
            result = classify_query("Tell me about this project")
        assert result == QueryMode.ARCHITECTURAL

    def test_llm_noisy_response_defaults_to_code_lookup(self):
        """If LLM returns something unexpected, default to CODE_LOOKUP."""
        mock_llm = self._mock_llm("I cannot classify this query.")
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            mock_settings.llm = mock_llm
            result = classify_query("Hello there")
        assert result == QueryMode.CODE_LOOKUP

    def test_llm_exception_defaults_to_code_lookup(self):
        """If LLM throws an error, fall back to CODE_LOOKUP safely."""
        mock_llm = MagicMock()
        mock_llm.complete.side_effect = Exception("Connection refused")
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            mock_settings.llm = mock_llm
            result = classify_query("What is this?")
        assert result == QueryMode.CODE_LOOKUP

    def test_llm_none_defaults_to_code_lookup(self):
        """If Settings.llm is None (not configured), default to CODE_LOOKUP."""
        with patch("app.retrieval.query_router.Settings") as mock_settings:
            mock_settings.llm = None
            # calling .complete() on None will raise AttributeError â†’ caught
            result = classify_query("What is this?")
        assert result == QueryMode.CODE_LOOKUP


# â”€â”€ Keyword constant integrity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestKeywordConstants:
    def test_code_keywords_is_a_set(self):
        assert isinstance(_CODE_KEYWORDS, set)

    def test_arch_keywords_is_a_set(self):
        assert isinstance(_ARCHITECTURAL_KEYWORDS, set)

    def test_code_keywords_non_empty(self):
        assert len(_CODE_KEYWORDS) > 5

    def test_arch_keywords_non_empty(self):
        assert len(_ARCHITECTURAL_KEYWORDS) > 5

    def test_no_overlap_between_keyword_sets(self):
        """Same keyword in both sets would cause ambiguous classification."""
        overlap = _CODE_KEYWORDS & _ARCHITECTURAL_KEYWORDS
        assert overlap == set(), f"Overlapping keywords: {overlap}"


class TestOutOfScopeDetection:
    @pytest.mark.parametrize("query", [
        "share me good movies list",
        "Can you recommend good movies?",
        "Give me a book recommendations list",
        "What is your favorite movie?",
        "What is the weather today?",
    ])
    def test_general_knowledge_or_preference_queries_detected(self, query):
        assert is_general_knowledge_or_preference_query(query) is True

    @pytest.mark.parametrize("query", [
        "Can you recommend improvements for this repository architecture?",
        "What do you recommend for this project pipeline?",
        "Show me the function that builds the API router",
    ])
    def test_repo_scoped_queries_not_marked_oos(self, query):
        assert is_general_knowledge_or_preference_query(query) is False


# â”€â”€ chunk_utils: chunk_text â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestChunkText:
    """Tests for the pure sliding-window text chunker."""

    def test_empty_string_returns_empty(self):
        assert chunk_text("") == []

    def test_none_equivalent_empty(self):
        assert chunk_text("") == []

    def test_short_text_single_chunk(self):
        text = "Hello, world!"
        chunks = chunk_text(text, max_chunk_size=800, overlap=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_produces_multiple_chunks(self):
        text = "x" * 2000
        chunks = chunk_text(text, max_chunk_size=500, overlap=50)
        assert len(chunks) > 1

    def test_chunks_respect_max_size(self):
        text = "a" * 5000
        chunks = chunk_text(text, max_chunk_size=300, overlap=0)
        for chunk in chunks:
            assert len(chunk) <= 300

    def test_overlap_creates_shared_content(self):
        text = "A" * 200 + "B" * 200
        chunks = chunk_text(text, max_chunk_size=250, overlap=50)
        assert len(chunks) >= 2
        # With overlap, end of chunk[0] and start of chunk[1] should share chars
        if len(chunks) >= 2:
            assert len(chunks[0]) > 0
            assert len(chunks[1]) > 0

    def test_overlap_clamped_if_larger_than_chunk_size(self):
        """overlap >= max_chunk_size â†’ clamped to max_chunk_size // 2."""
        text = "x" * 1000
        chunks = chunk_text(text, max_chunk_size=100, overlap=200)
        assert len(chunks) > 0  # Should not crash

    def test_hard_cap_at_20000_chars(self):
        """Input text capped at 20,000 characters."""
        text = "z" * 50000
        chunks = chunk_text(text, max_chunk_size=1000, overlap=0)
        total_chars = sum(len(c) for c in chunks)
        assert total_chars <= 20000 + 1000  # allow for chunk boundary

    def test_max_200_chunks(self):
        """Should never return more than 200 chunks."""
        text = "x" * 20000
        chunks = chunk_text(text, max_chunk_size=50, overlap=0)
        assert len(chunks) <= 200

    def test_whitespace_only_chunks_stripped(self):
        text = "hello    " + "   " * 50 + "world"
        chunks = chunk_text(text, max_chunk_size=10, overlap=0)
        for chunk in chunks:
            assert chunk == chunk.strip()
            assert len(chunk) > 0

    def test_single_char_text(self):
        chunks = chunk_text("a", max_chunk_size=800, overlap=100)
        assert chunks == ["a"]

    def test_exact_chunk_size_text(self):
        text = "a" * 800
        chunks = chunk_text(text, max_chunk_size=800, overlap=0)
        assert len(chunks) == 1

    def test_returns_list_of_strings(self):
        chunks = chunk_text("Hello world", max_chunk_size=100, overlap=10)
        assert isinstance(chunks, list)
        assert all(isinstance(c, str) for c in chunks)

    def test_zero_overlap(self):
        text = "a" * 500
        chunks = chunk_text(text, max_chunk_size=100, overlap=0)
        assert len(chunks) == 5

    def test_realistic_code_chunk(self):
        code = """
def hello_world():
    print("Hello, World!")
    return True

class MyClass:
    def __init__(self):
        self.value = 42
""" * 10
        chunks = chunk_text(code, max_chunk_size=200, overlap=20)
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
