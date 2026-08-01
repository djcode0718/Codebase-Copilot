import sys
import os
from unittest.mock import MagicMock, patch
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core import Settings
from llama_index.core.base.llms.types import ChatMessage
from app.services.qa_service import resolve_ambiguous_query


class TestQueryResolution:
    @pytest.fixture
    def mock_llm(self):
        from app.llm.llm_client import get_llm
        if Settings.llm is None:
            Settings.llm = get_llm()
        with patch.object(Settings.llm.__class__, "complete") as mock_complete:
            yield mock_complete

    def test_resolve_query_returns_original_if_no_memory(self, mock_llm):
        # If memory is None, it should immediately return the original query
        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, None)
        assert resolved == query
        mock_llm.assert_not_called()

    def test_resolve_query_returns_original_if_history_empty(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, memory)
        assert resolved == query
        mock_llm.assert_not_called()

    def test_resolve_query_calls_llm_when_history_present(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        memory.put(ChatMessage(role="user", content="Tell me about the class Config"))
        memory.put(ChatMessage(role="assistant", content="The Config class holds configuration settings like DB_URL."))

        # Set mock LLM return value
        mock_llm.return_value = "What is the purpose of the Config class?"

        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, memory)

        assert resolved == "What is the purpose of the Config class?"
        mock_llm.assert_called_once()

    def test_resolve_query_strips_preambles_and_quotes(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        memory.put(ChatMessage(role="user", content="Tell me about class Config"))
        memory.put(ChatMessage(role="assistant", content="Config holds DB settings."))

        # LLM returns standalone prefix and quotes
        mock_llm.return_value = 'Standalone question: "What does Config class represent?"'

        query = "what does it represent?"
        resolved = resolve_ambiguous_query(query, memory)

        assert resolved == "What does Config class represent?"

    def test_resolve_query_returns_original_on_llm_failure(self, mock_llm):
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        memory.put(ChatMessage(role="user", content="Tell me about class Config"))
        memory.put(ChatMessage(role="assistant", content="Config holds DB settings."))

        # LLM complete throws exception
        mock_llm.side_effect = Exception("LLM crash")

        query = "what is its purpose?"
        resolved = resolve_ambiguous_query(query, memory)

        # Fallback to original
        assert resolved == query
