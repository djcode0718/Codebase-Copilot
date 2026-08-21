"""
tests/test_supabase_service.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Unit tests for api/services/supabase_service.py.
All Supabase calls are mocked â€” no real DB connection needed.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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


# â”€â”€ Repositories â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


class TestUpdateRepoLlmProvider:
    def test_updates_provider_label(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.update_repo_llm_provider(mock, "repo-1", "Groq:llama-3.3-70b-versatile")

        mock.table.assert_called_with("repositories")
        mock.table.return_value.update.assert_called_once_with(
            {"llm_provider": "Groq:llama-3.3-70b-versatile"}
        )

    def test_skips_empty_provider_label(self):
        mock = MagicMock()

        supabase_service.update_repo_llm_provider(mock, "repo-1", "   ")

        mock.table.assert_not_called()


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


class TestRepoWorkspaceContext:
    def test_updates_workspace_context_in_memory(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.update_repo_workspace_context(
            mock,
            "repo-ctx-1",
            active_branch="feature/payment",
            default_branch="main",
            active_commit_sha="abc123",
            recent_branch="feature/payment",
        )

        ctx = supabase_service.get_repo_workspace_context({"id": "repo-ctx-1"})
        assert ctx["active_branch"] == "feature/payment"
        assert ctx["default_branch"] == "main"
        assert ctx["active_commit_sha"] == "abc123"
        assert ctx["recent_branches"][0] == "feature/payment"

    def test_uses_in_memory_when_columns_missing(self):
        class MissingColumnError(Exception):
            def __str__(self):
                return "column repositories.active_branch does not exist"

        mock = MagicMock()
        update_chain = MagicMock()
        update_chain.execute.side_effect = MissingColumnError()
        mock.table.return_value.update.return_value.eq.return_value = update_chain

        supabase_service.update_repo_workspace_context(
            mock,
            "repo-ctx-2",
            active_branch="hotfix/login",
            default_branch="main",
            active_commit_sha="def456",
            recent_branch="hotfix/login",
        )

        ctx = supabase_service.get_repo_workspace_context({"id": "repo-ctx-2"})
        assert ctx["active_branch"] == "hotfix/login"


class TestRecommendationLifecycle:
    def test_canonical_status_maps_legacy_values(self):
        assert supabase_service._canonical_recommendation_status("OPEN") == "NEW"
        assert supabase_service._canonical_recommendation_status("accepted") == "ACKNOWLEDGED"
        assert supabase_service._canonical_recommendation_status("verified") == "RESOLVED"

    def test_upsert_accepts_lowercase_lifecycle_status(self):
        mock = MagicMock()

        existing_chain = MagicMock()
        existing_chain.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{"status": "ACKNOWLEDGED", "fingerprint": "fp-1"}])

        table = MagicMock()
        table.select.return_value = existing_chain
        table.insert.return_value = insert_chain
        mock.table.return_value = table

        result = supabase_service.upsert_health_recommendation_state(
            mock,
            repo_id="repo-1",
            user_id="user-1",
            fingerprint="fp-1",
            category="Security",
            title="Harden auth",
            status="accepted",
            dismissed_reason=None,
        )

        assert result is not None
        payload = table.insert.call_args.args[0]
        assert payload["status"] == "ACKNOWLEDGED"

    def test_upsert_maps_legacy_dismissed_to_ignored_with_reason(self):
        mock = MagicMock()

        existing_chain = MagicMock()
        existing_chain.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{"status": "IGNORED", "fingerprint": "fp-2"}])

        table = MagicMock()
        table.select.return_value = existing_chain
        table.insert.return_value = insert_chain
        mock.table.return_value = table

        result = supabase_service.upsert_health_recommendation_state(
            mock,
            repo_id="repo-1",
            user_id="user-1",
            fingerprint="fp-2",
            category="Security",
            title="Remove hard-coded secrets",
            status="DISMISSED",
            dismissed_reason="False positive in generated recommendation",
        )

        assert result is not None
        payload = table.insert.call_args.args[0]
        assert payload["status"] == "IGNORED"
        assert payload["dismissed_reason"] == "False positive in generated recommendation"


# â”€â”€ Chats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    def test_retries_with_legacy_columns_when_new_columns_missing(self):
        class MissingColumnError(Exception):
            def __str__(self):
                return "Could not find the 'deleted_at' column of 'chats' in the schema cache"

        mock = MagicMock()
        insert_obj = MagicMock()
        insert_obj.execute.side_effect = [MissingColumnError(), MagicMock(data=[{"id": "chat-legacy", "repo_id": "repo-1"}])]
        mock.table.return_value.insert.return_value = insert_obj

        result = supabase_service.create_chat(mock, user_id="user-1", repo_id="repo-1", session_type="main")
        assert result["id"] == "chat-legacy"


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

    def test_falls_back_when_deleted_at_column_missing(self):
        class MissingColumnError(Exception):
            def __str__(self):
                return "column chats.deleted_at does not exist"

        mock = MagicMock()

        primary_query = MagicMock()
        primary_query.order.return_value.order.return_value.range.return_value.execute.side_effect = MissingColumnError()
        fallback_query = MagicMock()
        fallback_query.order.return_value.execute.return_value = MagicMock(data=[{"id": "c1"}])

        call_count = {"n": 0}

        def eq_side_effect(*_args, **_kwargs):
            call_count["n"] += 1
            return primary_query if call_count["n"] == 1 else fallback_query

        mock.table.return_value.select.return_value.eq.side_effect = eq_side_effect

        result = supabase_service.get_chats_for_repo(mock, "repo-1")
        assert len(result) == 1


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


class TestUpdateChatFields:
    def test_updates_arbitrary_fields(self):
        mock = MagicMock()
        chain = MagicMock()
        mock.table.return_value.update.return_value.eq.return_value = chain

        supabase_service.update_chat_fields(mock, "chat-1", {"is_pinned": True})
        mock.table.assert_called_with("chats")
        mock.table.return_value.update.assert_called_once()


class TestSoftDeleteChats:
    def test_scopes_batch_delete_by_user_and_repo(self):
        mock = MagicMock()
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.execute.return_value = MagicMock(data=[{"id": "c1"}, {"id": "c2"}])
        mock.table.return_value.update.return_value = chain

        count = supabase_service.soft_delete_chats(mock, chat_ids=["c1", "c2"], user_id="u1", repo_id="r1")

        assert count == 2
        mock.table.assert_called_with("chats")
        chain.eq.assert_any_call("user_id", "u1")
        chain.in_.assert_called_once_with("id", ["c1", "c2"])
        chain.eq.assert_any_call("repo_id", "r1")


# â”€â”€ Messages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    def test_saves_enriched_message_metadata(self):
        mock = MagicMock()
        select_chain = MagicMock()
        select_chain.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        count_chain = MagicMock()
        count_chain.eq.return_value.execute.return_value = MagicMock(data=[{"id": "m1"}])
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[])
        update_chain = MagicMock()
        update_chain.eq.return_value.execute.return_value = MagicMock(data=[])

        def table_side_effect(name):
            table = MagicMock()
            if name == "messages":
                table.select.side_effect = [select_chain, count_chain]
                table.insert.return_value = insert_chain
            else:
                table.update.return_value = update_chain
            return table

        mock.table.side_effect = table_side_effect
        result = supabase_service.save_message(
            mock,
            "chat-1",
            "assistant",
            "Answer",
            token_count=12,
            llm_provider="groq",
            llm_model="llama",
            metadata={"repo_id": "repo-1"},
        )

        inserted = insert_chain.execute.call_args_list
        assert result["token_count"] == 12
        assert result["llm_provider"] == "groq"
        assert inserted is not None

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


class TestConversationSummaries:
    def test_get_summary_returns_first_row(self):
        mock = make_supabase_mock(return_data=[{"id": "s1", "chat_id": "c1"}])
        result = supabase_service.get_conversation_summary(mock, "c1")
        assert result["id"] == "s1"

    def test_upsert_summary_insert_path(self):
        mock = make_supabase_mock(return_data=[])
        mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "s1"}])
        result = supabase_service.upsert_conversation_summary(
            mock,
            chat_id="c1",
            repo_id="r1",
            user_id="u1",
            payload={"executive_summary": "x"},
        )
        assert result["id"] == "s1"


class TestConversationTags:
    def test_replace_tags_runs_delete_then_insert(self):
        mock = MagicMock()
        del_chain = MagicMock()
        ins_chain = MagicMock()
        mock.table.return_value.delete.return_value.eq.return_value = del_chain
        mock.table.return_value.insert.return_value = ins_chain

        supabase_service.replace_conversation_tags(mock, chat_id="c1", tags=["security", "jwt"])
        mock.table.assert_any_call("conversation_tags")


class TestAttachments:
    def test_create_attachment(self):
        expected = {"id": "att-1", "chat_id": "c1", "user_id": "u1", "filename": "a.txt", "storage_path": "x/a.txt"}
        mock = make_supabase_mock(return_data=[expected])
        result = supabase_service.create_attachment(
            mock,
            chat_id="c1",
            user_id="u1",
            filename="a.txt",
            storage_path="x/a.txt",
        )
        assert result["id"] == "att-1"

    def test_get_attachments_for_chat(self):
        rows = [{"id": "att-1", "chat_id": "c1"}]
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        mock.table.return_value.select.return_value.eq.return_value.is_.return_value.order.return_value = chain
        result = supabase_service.get_attachments_for_chat(mock, chat_id="c1")
        assert len(result) == 1


class TestSavedReports:
    def test_create_saved_report(self):
        expected = {"id": "rep-1", "repo_id": "r1", "user_id": "u1", "report_type": "security", "content": {}}
        mock = make_supabase_mock(return_data=[expected])
        result = supabase_service.create_saved_report(
            mock,
            repo_id="r1",
            user_id="u1",
            report_type="security",
            title="S1",
            content={},
        )
        assert result["id"] == "rep-1"

    def test_get_saved_reports_for_repo(self):
        rows = [{"id": "rep-1", "repo_id": "r1", "user_id": "u1"}]
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        mock.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.order.return_value = chain
        result = supabase_service.get_saved_reports_for_repo(mock, repo_id="r1", user_id="u1")
        assert len(result) == 1


# â”€â”€ Evaluations â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


class TestRepositoryReviews:
    def test_insert_repository_review_returns_inserted(self):
        expected = {"id": "rv-1", "repo_id": "r1", "target_type": "file"}
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[expected])
        mock.table.return_value.insert.return_value = chain

        with patch("api.services.supabase_service.is_repository_review_schema_available", return_value=True):
            result = supabase_service.insert_repository_review(
                mock,
                repo_id="r1",
                user_id="u1",
                target_type="file",
                summary="done",
                findings=[],
                changed_files=["api/routers/chat.py"],
            )

        assert result["id"] == "rv-1"

    def test_list_repository_reviews_returns_rows(self):
        rows = [{"id": "rv-1"}, {"id": "rv-2"}]
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=rows)
        mock.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value = chain

        with patch("api.services.supabase_service.is_repository_review_schema_available", return_value=True):
            result = supabase_service.list_repository_reviews(mock, repo_id="r1", user_id="u1", limit=20)

        assert len(result) == 2

    def test_get_repository_review_by_id(self):
        row = {"id": "rv-1", "repo_id": "r1"}
        mock = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[row])
        mock.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value = chain

        with patch("api.services.supabase_service.is_repository_review_schema_available", return_value=True):
            result = supabase_service.get_repository_review_by_id(mock, review_id="rv-1", user_id="u1")

        assert result and result["id"] == "rv-1"


