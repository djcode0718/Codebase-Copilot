import sys
import os
from unittest.mock import MagicMock, patch
import pytest

pytestmark = pytest.mark.slow
pytest.importorskip("llama_index.core")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Stub heavy / unavailable modules before importing qa_service
for _mod in [
    "llama_index.retrievers",
    "llama_index.retrievers.bm25",
    "llama_index.embeddings.ollama",
    "app.indexing.index_builder",
    "app.retrieval.reranker",
]:
    sys.modules.setdefault(_mod, MagicMock())

from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage
from app.services.qa_service import resolve_ambiguous_query


class TestQueryResolution:
    @pytest.fixture(autouse=True)
    def mock_llm(self):
        """Inject a MagicMock as Settings._llm so no real LLM is ever instantiated."""
        mock = MagicMock()
        original = Settings.__dict__.get("_llm", MagicMock())
        Settings._llm = mock
        yield mock
        Settings._llm = original

    def test_resolve_query_returns_original_if_no_memory(self, mock_llm):
        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, None)
        assert resolved == query
        mock_llm.complete.assert_not_called()

    def test_resolve_query_returns_original_if_history_empty(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, memory)
        assert resolved == query
        mock_llm.complete.assert_not_called()

    def test_resolve_query_calls_llm_when_history_present(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        memory.put(ChatMessage(role="user", content="Tell me about the class Config"))
        memory.put(ChatMessage(role="assistant", content="The Config class holds configuration settings like DB_URL."))

        mock_llm.complete.return_value = "What is the purpose of the Config class?"

        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, memory)

        assert resolved == "What is the purpose of the Config class?"
        mock_llm.complete.assert_called_once()

    def test_resolve_query_strips_preambles_and_quotes(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        memory.put(ChatMessage(role="user", content="Tell me about class Config"))
        memory.put(ChatMessage(role="assistant", content="Config holds DB settings."))

        mock_llm.complete.return_value = 'Standalone question: "What does Config class represent?"'

        query = "what does it represent?"
        resolved = resolve_ambiguous_query(query, memory)

        assert resolved == "What does Config class represent?"

    def test_resolve_query_returns_original_on_llm_failure(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        memory.put(ChatMessage(role="user", content="Tell me about class Config"))
        memory.put(ChatMessage(role="assistant", content="Config holds DB settings."))

        mock_llm.complete.side_effect = Exception("LLM crash")

        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, memory)

        assert resolved == query
