"""
tests/test_supabase_service.py
────────────────────────────────
Unit tests for api/services/supabase_service.py.
All Supabase calls are mocked — no real DB connection needed.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from api.services import supabase_service


def make_supabase_mock(return_data=None):
    """Helper to build a chained Supabase mock that returns given data."""
    mock = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=return_data or [])

    # Support .table().select().eq().execute(), .insert().execute(), etc.
    mock.table.return_value.select.return_value = chain
    mock.table.return_value.select.return_value.eq.return_value = chain
    mock.table.return_value.select.return_value.eq.return_value.order.return_value = chain
    mock.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value = chain
    mock.table.return_value.insert.return_value = chain
    mock.table.return_value.update.return_value.eq.return_value = chain
    mock.table.return_value.delete.return_value.eq.return_value = chain
    return mock


# ── Repositories ──────────────────────────────────────────────────────────────

class TestCreateRepoRecord:
    def test_returns_inserted_record(self):
        expected = {"id": "repo-1", "name": "my-repo", "status": "indexing"}
        mock = make_supabase_mock(return_data=[expected])

        result = supabase_service.create_repo_record(
            mock,
            user_id="user-1",
            name="my-repo",
            source_url="https://github.com/x/y",
            index_name="my-repo",
            llm_provider="groq",
        )
        assert result == expected

    def test_returns_local_record_if_no_data(self):
        mock = make_supabase_mock(return_data=[])

        result = supabase_service.create_repo_record(
            mock,
            user_id="user-1",
            name="my-repo",
            source_url="https://github.com/x/y",
            index_name="my-repo",
            llm_provider="groq",
        )
        assert result["name"] == "my-repo"
        assert result["status"] == "indexing"
        assert "id" in result


class TestGetRepo:
    def test_returns_repo_if_found(self):
        repo_data = {"id": "repo-1", "name": "test", "status": "ready"}
        mock = make_supabase_mock(return_data=[repo_data])

        result = supabase_service.get_repo(mock, "repo-1")
        assert result["id"] == "repo-1"

    def test_returns_none_if_not_found(self):
        mock = make_supabase_mock(return_data=[])

        result = supabase_service.get_repo(mock, "nonexistent")
        assert result is None


class TestGetReposForUser:
    def test_returns_list(self):
        repos = [
            {"id": "r1", "name": "repo1"},
            {"id": "r2", "name": "repo2"},
        ]
        mock = make_supabase_mock(return_data=repos)
        result = supabase_service.get_repos_for_user(mock, "user-1")
        assert len(result) == 2

    def test_returns_empty_list_if_none(self):
        mock = make_supabase_mock(return_data=None)
        result = supabase_service.get_repos_for_user(mock, "user-1")
        assert result == []


class TestUpdateRepoStatus:
    def test_calls_update(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.update_repo_status(mock, "repo-1", "ready", file_count=10, node_count=50)
        mock.table.assert_called_with("repositories")
        mock.table.return_value.update.assert_called_once()

    def test_calls_update_without_counts(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.update_repo_status(mock, "repo-1", "failed")
        mock.table.assert_called_with("repositories")


class TestResetRepoForReindex:
    def test_sets_repo_back_to_indexing_state(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.reset_repo_for_reindex(mock, "repo-1")

        mock.table.assert_called_with("repositories")
        mock.table.return_value.update.assert_called_once_with({
            "status": "indexing",
            "file_count": None,
            "node_count": None,
            "indexed_at": None,
        })


class TestDeleteRepo:
    def test_calls_delete(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.delete.return_value.eq.return_value = chain

        supabase_service.delete_repo(mock, "repo-1")
        mock.table.assert_called_with("repositories")
        mock.table.return_value.delete.assert_called_once()


# ── Chats ─────────────────────────────────────────────────────────────────────

class TestCreateChat:
    def test_returns_chat_record(self):
        chat = {"id": "chat-1", "user_id": "user-1", "repo_id": "repo-1"}
        mock = make_supabase_mock(return_data=[chat])

        result = supabase_service.create_chat(mock, user_id="user-1", repo_id="repo-1")
        assert result["id"] == "chat-1"

    def test_fallback_local_record(self):
        mock = make_supabase_mock(return_data=[])

        result = supabase_service.create_chat(mock, user_id="user-1", repo_id="repo-1")
        assert "id" in result
        assert result["repo_id"] == "repo-1"


class TestGetChat:
    def test_returns_chat(self):
        chat = {"id": "chat-1", "user_id": "user-1", "repo_id": "repo-1"}
        mock = make_supabase_mock(return_data=[chat])
        result = supabase_service.get_chat(mock, "chat-1")
        assert result["id"] == "chat-1"

    def test_returns_none_if_not_found(self):
        mock = make_supabase_mock(return_data=[])
        result = supabase_service.get_chat(mock, "bad-id")
        assert result is None


class TestGetChatsForRepo:
    def test_returns_list(self):
        chats = [{"id": "c1"}, {"id": "c2"}]
        mock = make_supabase_mock(return_data=chats)
        result = supabase_service.get_chats_for_repo(mock, "repo-1")
        assert len(result) == 2

    def test_returns_empty_if_none(self):
        mock = make_supabase_mock(return_data=None)
        result = supabase_service.get_chats_for_repo(mock, "repo-1")
        assert result == []


class TestDeleteChat:
    def test_calls_delete(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.delete.return_value.eq.return_value = chain

        supabase_service.delete_chat(mock, "chat-1")
        mock.table.assert_called_with("chats")


class TestUpdateChatTitle:
    def test_calls_update(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.update_chat_title(mock, "chat-1", "New title")
        mock.table.return_value.update.assert_called_once()


# ── Messages ──────────────────────────────────────────────────────────────────

class TestSaveMessage:
    def test_saves_user_message(self):
        msg = {"id": "msg-1", "role": "user", "content": "Hello"}
        mock = make_supabase_mock(return_data=[msg])

        result = supabase_service.save_message(mock, "chat-1", "user", "Hello")
        assert result["role"] == "user"

    def test_saves_with_optional_fields(self):
        msg = {"id": "msg-2", "role": "assistant", "content": "Answer",
               "query_mode": "code_lookup", "latency_ms": 500}
        mock = make_supabase_mock(return_data=[msg])

        result = supabase_service.save_message(
            mock, "chat-1", "assistant", "Answer",
            query_mode="code_lookup",
            retrieved_files=[{"path": "main.py", "score": 0.9}],
            latency_ms=500,
        )
        assert result["query_mode"] == "code_lookup"

    def test_fallback_when_no_data(self):
        mock = make_supabase_mock(return_data=[])
        result = supabase_service.save_message(mock, "chat-1", "user", "Hi")
        assert result["content"] == "Hi"
        assert result["role"] == "user"


class TestGetMessagesForChat:
    def test_returns_ordered_messages(self):
        msgs = [
            {"id": "m1", "role": "user", "content": "Q1"},
            {"id": "m2", "role": "assistant", "content": "A1"},
        ]
        mock = make_supabase_mock(return_data=msgs)
        result = supabase_service.get_messages_for_chat(mock, "chat-1")
        assert len(result) == 2
        assert result[0]["role"] == "user"

    def test_returns_empty_list_if_none(self):
        mock = make_supabase_mock(return_data=None)
        result = supabase_service.get_messages_for_chat(mock, "chat-1")
        assert result == []


# ── Evaluations ───────────────────────────────────────────────────────────────

class TestSaveEvaluation:
    def test_saves_full_summary(self):
        summary = {
            "hit_rate": 0.9,
            "mrr": 0.85,
            "avg_faithfulness": 0.8,
            "avg_relevancy": 0.75,
            "mode_accuracy": 0.95,
            "avg_latency_total": 1200.0,
            "avg_latency_retrieval": 300.0,
            "avg_latency_rerank": 100.0,
            "avg_latency_llm": 800.0,
            "colbert_enabled": False,
        }
        expected = {"id": "eval-1", **summary}
        mock = make_supabase_mock(return_data=[expected])

        result = supabase_service.save_evaluation(
            mock, repo_id="repo-1", user_id="user-1", summary=summary
        )
        assert result["hit_rate"] == 0.9

    def test_fallback_local_record(self):
        mock = make_supabase_mock(return_data=[])
        summary = {"hit_rate": 0.5}
        result = supabase_service.save_evaluation(mock, "r1", "u1", summary)
        assert "id" in result


class TestGetLatestEvaluation:
    def test_returns_latest(self):
        eval_data = {"id": "eval-1", "hit_rate": 0.9}
        mock = make_supabase_mock(return_data=[eval_data])
        result = supabase_service.get_latest_evaluation(mock, "repo-1")
        assert result["id"] == "eval-1"

    def test_returns_none_if_no_eval(self):
        mock = make_supabase_mock(return_data=[])
        result = supabase_service.get_latest_evaluation(mock, "repo-1")
        assert result is None
