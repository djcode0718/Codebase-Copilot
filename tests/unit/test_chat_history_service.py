"""
Unit tests for api/services/chat_history_service.py
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture()
def mock_supabase():
    return MagicMock()


@pytest.fixture()
def stub_supabase_service():
    """Patch supabase_service as imported inside chat_history_service."""
    with patch("api.services.chat_history_service.supabase_service") as svc:
        yield svc


# ─── get_chat_history ────────────────────────────────────────────────────────

def test_get_chat_history_delegates(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_chat_history

    expected = [{"id": "1", "content": "hello"}]
    stub_supabase_service.get_messages_for_chat.return_value = expected

    result = get_chat_history(mock_supabase, "chat-abc")

    stub_supabase_service.get_messages_for_chat.assert_called_once_with(
        mock_supabase, "chat-abc"
    )
    assert result == expected


def test_get_chat_history_returns_empty_list(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_chat_history

    stub_supabase_service.get_messages_for_chat.return_value = []
    result = get_chat_history(mock_supabase, "chat-xyz")
    assert result == []


def test_get_chat_history_propagates_exception(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_chat_history

    stub_supabase_service.get_messages_for_chat.side_effect = RuntimeError("db down")
    with pytest.raises(RuntimeError, match="db down"):
        get_chat_history(mock_supabase, "chat-fail")


# ─── get_repo_memory_messages ────────────────────────────────────────────────

def test_get_repo_memory_messages_default_args(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_repo_memory_messages

    stub_supabase_service.get_recent_messages_for_repo.return_value = []
    get_repo_memory_messages(mock_supabase, "repo-1")

    stub_supabase_service.get_recent_messages_for_repo.assert_called_once_with(
        mock_supabase, "repo-1", exclude_chat_id=None, limit=30
    )


def test_get_repo_memory_messages_with_exclude(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_repo_memory_messages

    stub_supabase_service.get_recent_messages_for_repo.return_value = [{"id": "m1"}]
    result = get_repo_memory_messages(
        mock_supabase, "repo-2", exclude_chat_id="chat-99", limit=10
    )

    stub_supabase_service.get_recent_messages_for_repo.assert_called_once_with(
        mock_supabase, "repo-2", exclude_chat_id="chat-99", limit=10
    )
    assert result == [{"id": "m1"}]


def test_get_repo_memory_messages_propagates_exception(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_repo_memory_messages

    stub_supabase_service.get_recent_messages_for_repo.side_effect = ConnectionError("timeout")
    with pytest.raises(ConnectionError):
        get_repo_memory_messages(mock_supabase, "repo-3")


# ─── get_repo_conversation_summaries ─────────────────────────────────────────

def test_get_repo_conversation_summaries_delegates(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_repo_conversation_summaries

    expected = [{"id": "s1", "summary": "foo"}]
    stub_supabase_service.get_conversation_summaries_for_repo.return_value = expected

    result = get_repo_conversation_summaries(
        mock_supabase, repo_id="repo-A", user_id="user-1"
    )

    stub_supabase_service.get_conversation_summaries_for_repo.assert_called_once_with(
        mock_supabase, repo_id="repo-A", user_id="user-1", limit=200
    )
    assert result == expected


def test_get_repo_conversation_summaries_custom_limit(mock_supabase, stub_supabase_service):
    from api.services.chat_history_service import get_repo_conversation_summaries

    stub_supabase_service.get_conversation_summaries_for_repo.return_value = []
    get_repo_conversation_summaries(
        mock_supabase, repo_id="repo-B", user_id="user-2", limit=50
    )

    stub_supabase_service.get_conversation_summaries_for_repo.assert_called_once_with(
        mock_supabase, repo_id="repo-B", user_id="user-2", limit=50
    )


def test_get_repo_conversation_summaries_propagates_exception(
    mock_supabase, stub_supabase_service
):
    from api.services.chat_history_service import get_repo_conversation_summaries

    stub_supabase_service.get_conversation_summaries_for_repo.side_effect = ValueError("bad")
    with pytest.raises(ValueError, match="bad"):
        get_repo_conversation_summaries(mock_supabase, repo_id="r", user_id="u")
