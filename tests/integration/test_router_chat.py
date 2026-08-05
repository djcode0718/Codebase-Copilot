"""
tests/test_router_chat.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Integration tests for the chat router endpoints:
  POST   /api/chat/session
  GET    /api/chat/list?repo_id=...
  GET    /api/chat/{chat_id}/messages
  DELETE /api/chat/{chat_id}

SSE streaming (/message/stream) is tested separately.
All external dependencies (Supabase, LLM) are mocked.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import patch, MagicMock


# â”€â”€ POST /api/chat/session â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestCreateChatSession:
    def _setup_repo_and_chat(self, mock_supabase, fake_repo, fake_chat):
        """Wire mock to return fake_repo on get_repo and fake_chat on create_chat."""
        chain = MagicMock()

        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "repositories":
                eq_chain = MagicMock()
                eq_chain.execute.return_value = MagicMock(data=[fake_repo])
                mock_table.select.return_value.eq.return_value = eq_chain
            elif table_name == "chats":
                ins_chain = MagicMock()
                ins_chain.execute.return_value = MagicMock(data=[fake_chat])
                mock_table.insert.return_value = ins_chain
            return mock_table

        mock_supabase.table.side_effect = table_side_effect

    def test_creates_session_for_ready_repo(
        self, client, mock_supabase, fake_repo, fake_chat, fake_repo_id, fake_chat_id
    ):
        self._setup_repo_and_chat(mock_supabase, fake_repo, fake_chat)

        resp = client.post("/api/chat/session", json={"repo_id": fake_repo_id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["chat_id"] == fake_chat_id
        assert body["repo_id"] == fake_repo_id

    def test_fails_if_repo_not_found(self, client, mock_supabase, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post("/api/chat/session", json={"repo_id": fake_repo_id})
        assert resp.status_code == 404

    def test_fails_if_repo_not_ready(self, client, mock_supabase, fake_user_id, fake_repo_id):
        indexing_repo = {
            "id": fake_repo_id,
            "user_id": fake_user_id,
            "status": "indexing",
            "name": "test",
            "source_url": "https://github.com/x/y",
            "index_name": "y",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[indexing_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post("/api/chat/session", json={"repo_id": fake_repo_id})
        assert resp.status_code == 400
        assert "not ready" in resp.json()["detail"].lower()

    def test_fails_if_repo_owned_by_other_user(self, client, mock_supabase, fake_repo_id):
        repo_other = {
            "id": fake_repo_id,
            "user_id": "other-user",
            "status": "ready",
            "name": "test",
            "source_url": "https://github.com/x/y",
            "index_name": "y",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[repo_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post("/api/chat/session", json={"repo_id": fake_repo_id})
        assert resp.status_code == 403

    def test_missing_repo_id_returns_422(self, client):
        resp = client.post("/api/chat/session", json={})
        assert resp.status_code == 422

    def test_main_session_works_with_legacy_chat_schema(self, client, mock_supabase, fake_repo_id, fake_user_id):
        class MissingColumnError(Exception):
            def __str__(self):
                return "column chats.session_type does not exist"

        repo_row = {
            "id": fake_repo_id,
            "user_id": fake_user_id,
            "status": "ready",
            "name": "repo",
            "source_url": "https://github.com/example/repo",
            "index_name": "repo",
        }

        chats_table = MagicMock()
        # get_main_chat_for_repo query fails on session_type/deleted_at in legacy schema
        chats_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.is_.return_value.limit.return_value.execute.side_effect = MissingColumnError()
        # fallback lookup by title returns no main session yet
        chats_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        # create_chat first insert fails on new columns, second insert succeeds with legacy payload
        insert_chain = MagicMock()
        insert_chain.execute.side_effect = [MissingColumnError(), MagicMock(data=[{"id": "legacy-main", "repo_id": fake_repo_id}])]
        chats_table.insert.return_value = insert_chain

        repos_table = MagicMock()
        repos_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[repo_row])

        def table_side_effect(table_name):
            if table_name == "repositories":
                return repos_table
            if table_name == "chats":
                return chats_table
            return MagicMock()

        mock_supabase.table.side_effect = table_side_effect
        resp = client.post("/api/chat/session/main", json={"repo_id": fake_repo_id})
        assert resp.status_code == 200
        assert resp.json()["chat_id"] == "legacy-main"


# â”€â”€ GET /api/chat/list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestListChats:
    def test_lists_chats_for_repo(self, client, mock_supabase, fake_chat, fake_repo_id):
        def table_side_effect(table_name):
            table = MagicMock()
            if table_name == "repositories":
                repo_chain = MagicMock()
                repo_chain.execute.return_value = MagicMock(data=[{"id": fake_repo_id, "user_id": "00000000-0000-0000-0000-000000000001", "status": "ready"}])
                table.select.return_value.eq.return_value = repo_chain
            elif table_name == "chats":
                chats_chain = MagicMock()
                chats_chain.execute.return_value = MagicMock(data=[fake_chat])
                table.select.return_value.eq.return_value.is_.return_value.order.return_value.order.return_value.range.return_value = chats_chain
            return table

        mock_supabase.table.side_effect = table_side_effect

        resp = client.get(f"/api/chat/list?repo_id={fake_repo_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body[0]["id"] == fake_chat["id"]

    def test_returns_empty_list(self, client, mock_supabase, fake_repo_id):
        def table_side_effect(table_name):
            table = MagicMock()
            if table_name == "repositories":
                repo_chain = MagicMock()
                repo_chain.execute.return_value = MagicMock(data=[{"id": fake_repo_id, "user_id": "00000000-0000-0000-0000-000000000001", "status": "ready"}])
                table.select.return_value.eq.return_value = repo_chain
            elif table_name == "chats":
                chats_chain = MagicMock()
                chats_chain.execute.return_value = MagicMock(data=[])
                table.select.return_value.eq.return_value.is_.return_value.order.return_value.order.return_value.range.return_value = chats_chain
            return table

        mock_supabase.table.side_effect = table_side_effect

        resp = client.get(f"/api/chat/list?repo_id={fake_repo_id}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_missing_repo_id_returns_422(self, client):
        resp = client.get("/api/chat/list")
        assert resp.status_code == 422


# â”€â”€ GET /api/chat/{chat_id}/messages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetMessages:
    def test_returns_messages(
        self, client, mock_supabase, fake_chat, fake_chat_id, fake_user_id, fake_message
    ):
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "chats":
                eq_chain = MagicMock()
                eq_chain.execute.return_value = MagicMock(data=[fake_chat])
                mock_table.select.return_value.eq.return_value = eq_chain
            elif table_name == "messages":
                order_chain = MagicMock()
                order_chain.execute.return_value = MagicMock(data=[fake_message])
                mock_table.select.return_value.eq.return_value.order.return_value = order_chain
            return mock_table

        mock_supabase.table.side_effect = table_side_effect

        resp = client.get(f"/api/chat/{fake_chat_id}/messages")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body[0]["role"] == "user"

    def test_returns_404_if_chat_not_found(self, client, mock_supabase, fake_chat_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get(f"/api/chat/{fake_chat_id}/messages")
        assert resp.status_code == 404

    def test_returns_403_if_not_owner(self, client, mock_supabase, fake_chat_id):
        chat_other = {
            "id": fake_chat_id,
            "user_id": "other-user",
            "repo_id": "some-repo",
            "title": None,
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[chat_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get(f"/api/chat/{fake_chat_id}/messages")
        assert resp.status_code == 403


# â”€â”€ DELETE /api/chat/{chat_id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestDeleteChat:
    def test_deletes_successfully(self, client, mock_supabase, fake_chat, fake_chat_id):
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "chats":
                # First call (get_chat) returns the chat
                eq_chain = MagicMock()
                eq_chain.execute.return_value = MagicMock(data=[fake_chat])
                mock_table.select.return_value.eq.return_value = eq_chain
                # Delete chain
                del_chain = MagicMock()
                del_chain.execute.return_value = MagicMock(data=[])
                mock_table.delete.return_value.eq.return_value = del_chain
            return mock_table

        mock_supabase.table.side_effect = table_side_effect

        resp = client.delete(f"/api/chat/{fake_chat_id}")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()


class TestConversationWorkspaceEndpoints:
    def test_patch_chat_updates_flags(self, client, mock_supabase, fake_chat, fake_chat_id):
        chats_table = MagicMock()
        get_chain = MagicMock()
        get_chain.execute.return_value = MagicMock(data=[fake_chat])
        chats_table.select.return_value.eq.return_value = get_chain
        update_chain = MagicMock()
        update_chain.execute.return_value = MagicMock(data=[])
        chats_table.update.return_value.eq.return_value = update_chain

        def mock_table(name):
            if name == "chats":
                return chats_table
            return MagicMock()

        mock_supabase.table.side_effect = mock_table
        resp = client.patch(f"/api/chat/{fake_chat_id}", json={"is_pinned": True})
        assert resp.status_code == 200

    def test_summary_endpoint_generates_payload(self, client, mock_supabase, fake_chat, fake_chat_id):
        chats_table = MagicMock()
        chat_chain = MagicMock()
        chat_chain.execute.return_value = MagicMock(data=[fake_chat])
        chats_table.select.return_value.eq.return_value = chat_chain

        messages_table = MagicMock()
        message_chain = MagicMock()
        message_chain.execute.return_value = MagicMock(data=[{"id": "m1", "chat_id": fake_chat_id, "role": "user", "content": "Review auth flow"}])
        messages_table.select.return_value.eq.return_value.order.return_value = message_chain

        summary_table = MagicMock()
        summary_table.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        summary_table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "s1", "chat_id": fake_chat_id}])

        tags_table = MagicMock()
        tags_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        tags_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        tags_table.insert.return_value.execute.return_value = MagicMock(data=[])

        def mock_table(name):
            if name == "chats":
                return chats_table
            if name == "messages":
                return messages_table
            if name == "conversation_summaries":
                return summary_table
            if name == "conversation_tags":
                return tags_table
            return MagicMock()

        mock_supabase.table.side_effect = mock_table
        resp = client.get(f"/api/chat/{fake_chat_id}/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["chat_id"] == fake_chat_id

    def test_delete_404_if_not_found(self, client, mock_supabase, fake_chat_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.delete(f"/api/chat/{fake_chat_id}")
        assert resp.status_code == 404

    def test_delete_403_if_not_owner(self, client, mock_supabase, fake_chat_id):
        chat_other = {
            "id": fake_chat_id,
            "user_id": "other-user",
            "repo_id": "some-repo",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[chat_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.delete(f"/api/chat/{fake_chat_id}")
        assert resp.status_code == 403


class TestAttachmentEndpoints:
    def test_create_and_list_attachments(self, client, mock_supabase, fake_chat, fake_chat_id):
        chats_table = MagicMock()
        chat_chain = MagicMock()
        chat_chain.execute.return_value = MagicMock(data=[fake_chat])
        chats_table.select.return_value.eq.return_value = chat_chain

        attachments_table = MagicMock()
        insert_chain = MagicMock()
        insert_chain.execute.return_value = MagicMock(data=[{
            "id": "att-1",
            "chat_id": fake_chat_id,
            "user_id": fake_chat["user_id"],
            "filename": "diagram.png",
            "storage_path": "repo/diagram.png",
        }])
        attachments_table.insert.return_value = insert_chain
        list_chain = MagicMock()
        list_chain.execute.return_value = MagicMock(data=[{
            "id": "att-1",
            "chat_id": fake_chat_id,
            "user_id": fake_chat["user_id"],
            "filename": "diagram.png",
            "storage_path": "repo/diagram.png",
        }])
        attachments_table.select.return_value.eq.return_value.is_.return_value.order.return_value = list_chain

        def mock_table(name):
            if name == "chats":
                return chats_table
            if name == "attachments":
                return attachments_table
            return MagicMock()

        mock_supabase.table.side_effect = mock_table
        create_resp = client.post(
            f"/api/chat/{fake_chat_id}/attachments",
            json={"filename": "diagram.png", "storage_path": "repo/diagram.png"},
        )
        assert create_resp.status_code == 200
        list_resp = client.get(f"/api/chat/{fake_chat_id}/attachments")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_attachment_get_update_delete(self, client, mock_supabase, fake_chat):
        attachments_table = MagicMock()
        get_chain = MagicMock()
        get_chain.execute.return_value = MagicMock(data=[{
            "id": "att-1",
            "chat_id": fake_chat["id"],
            "user_id": fake_chat["user_id"],
            "filename": "diagram.png",
            "storage_path": "repo/diagram.png",
        }])
        attachments_table.select.return_value.eq.return_value = get_chain
        update_chain = MagicMock()
        update_chain.execute.return_value = MagicMock(data=[])
        attachments_table.update.return_value.eq.return_value = update_chain
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=[])
        attachments_table.delete.return_value.eq.return_value = delete_chain

        def mock_table(name):
            if name == "attachments":
                return attachments_table
            return MagicMock()

        mock_supabase.table.side_effect = mock_table
        assert client.get("/api/chat/attachments/att-1").status_code == 200
        assert client.patch("/api/chat/attachments/att-1", json={"filename": "new.png"}).status_code == 200
        assert client.delete("/api/chat/attachments/att-1?hard_delete=true").status_code == 200

    def test_attachment_not_found(self, client, mock_supabase):
        attachments_table = MagicMock()
        attachments_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_supabase.table.side_effect = lambda name: attachments_table if name == "attachments" else MagicMock()
        assert client.get("/api/chat/attachments/missing").status_code == 404


class TestSavedReportEndpoints:
    def test_create_and_list_saved_reports(self, client, mock_supabase, fake_repo_id, fake_user_id):
        repo_table = MagicMock()
        repo_chain = MagicMock()
        repo_chain.execute.return_value = MagicMock(data=[{"id": fake_repo_id, "user_id": fake_user_id, "status": "ready"}])
        repo_table.select.return_value.eq.return_value = repo_chain

        reports_table = MagicMock()
        create_chain = MagicMock()
        create_chain.execute.return_value = MagicMock(data=[{
            "id": "rep-1",
            "repo_id": fake_repo_id,
            "user_id": fake_user_id,
            "report_type": "security",
            "title": "Auth review",
            "content": {"risk": "jwt"},
        }])
        reports_table.insert.return_value = create_chain
        list_chain = MagicMock()
        list_chain.execute.return_value = MagicMock(data=[{
            "id": "rep-1",
            "repo_id": fake_repo_id,
            "user_id": fake_user_id,
            "report_type": "security",
            "title": "Auth review",
            "content": {"risk": "jwt"},
        }])
        reports_table.select.return_value.eq.return_value.eq.return_value.is_.return_value.order.return_value = list_chain

        def mock_table(name):
            if name == "repositories":
                return repo_table
            if name == "saved_reports":
                return reports_table
            return MagicMock()

        mock_supabase.table.side_effect = mock_table
        create_resp = client.post(
            f"/api/chat/repo/{fake_repo_id}/reports",
            json={"report_type": "security", "title": "Auth review", "content": {"risk": "jwt"}},
        )
        assert create_resp.status_code == 200

        list_resp = client.get(f"/api/chat/repo/{fake_repo_id}/reports")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_report_get_update_delete(self, client, mock_supabase, fake_user_id):
        reports_table = MagicMock()
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[{
            "id": "rep-1",
            "repo_id": "r1",
            "user_id": fake_user_id,
            "report_type": "security",
            "title": "Auth review",
            "content": {"risk": "jwt"},
        }])
        reports_table.select.return_value.eq.return_value = select_chain
        update_chain = MagicMock()
        update_chain.execute.return_value = MagicMock(data=[])
        reports_table.update.return_value.eq.return_value = update_chain
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=[])
        reports_table.delete.return_value.eq.return_value = delete_chain

        mock_supabase.table.side_effect = lambda name: reports_table if name == "saved_reports" else MagicMock()
        assert client.get("/api/chat/reports/rep-1").status_code == 200
        assert client.patch("/api/chat/reports/rep-1", json={"title": "New"}).status_code == 200
        assert client.delete("/api/chat/reports/rep-1?hard_delete=true").status_code == 200

    def test_report_forbidden(self, client, mock_supabase):
        reports_table = MagicMock()
        reports_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{
            "id": "rep-1",
            "repo_id": "r1",
            "user_id": "other-user",
            "report_type": "security",
            "content": {},
        }])
        mock_supabase.table.side_effect = lambda name: reports_table if name == "saved_reports" else MagicMock()
        assert client.get("/api/chat/reports/rep-1").status_code == 403


# â”€â”€ POST /api/chat/{chat_id}/message/stream â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestStreamMessage:
    """Basic tests for the streaming endpoint (non-SSE response checks)."""

    def test_returns_400_if_query_empty(self, client, mock_supabase, fake_chat, fake_chat_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_chat])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(
            f"/api/chat/{fake_chat_id}/message/stream",
            json={"query": "   "},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_returns_404_if_chat_not_found(self, client, mock_supabase, fake_chat_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(
            f"/api/chat/{fake_chat_id}/message/stream",
            json={"query": "What does main.py do?"},
        )
        assert resp.status_code == 404

    def test_returns_403_if_not_owner(self, client, mock_supabase, fake_chat_id):
        chat_other = {
            "id": fake_chat_id,
            "user_id": "other-user",
            "repo_id": "some-repo",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[chat_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(
            f"/api/chat/{fake_chat_id}/message/stream",
            json={"query": "What does main.py do?"},
        )
        assert resp.status_code == 403

    def test_missing_query_returns_422(self, client):
        resp = client.post(
            "/api/chat/some-id/message/stream",
            json={},
        )
        assert resp.status_code == 422

    def test_stream_error_handling(self, client, mock_supabase, fake_chat, fake_chat_id, monkeypatch):
        # Mock chat lookup
        chat_chain = MagicMock()
        chat_chain.execute.return_value = MagicMock(data=[fake_chat])
        
        # Mock repository lookup
        repo_data = {
            "id": "some-repo",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "index_name": "some-index",
            "status": "ready",
        }
        repo_chain = MagicMock()
        repo_chain.execute.return_value = MagicMock(data=[repo_data])
        
        # Setup mock tables
        chats_table = MagicMock()
        chats_table.select.return_value.eq.return_value = chat_chain
        
        repos_table = MagicMock()
        repos_table.select.return_value.eq.return_value = repo_chain
        
        def mock_table(table_name):
            if table_name == "chats":
                return chats_table
            elif table_name == "repositories":
                return repos_table
            return MagicMock()
            
        monkeypatch.setattr(mock_supabase, "table", mock_table)

        # Mock stream_chat_response provider to raise an exception mid-stream
        async def mock_stream(*args, **kwargs):
            yield 'data: {"type": "token", "content": "Start"}\n\n'
            raise RuntimeError("Mid-stream connection error")

        monkeypatch.setattr("api.routers.chat._get_stream_chat_response_callable", lambda: mock_stream)

        # Trigger stream request
        resp = client.post(
            f"/api/chat/{fake_chat_id}/message/stream",
            json={"query": "Let's trigger an error"},
        )
        assert resp.status_code == 200
        
        # Read the response SSE stream lines
        chunks = [(line.decode("utf-8") if isinstance(line, bytes) else line) for line in resp.iter_lines() if line]
        assert len(chunks) == 3  # token + error + done
        assert "token" in chunks[0]
        assert "error" in chunks[1]
        assert "internal error" in chunks[1].lower()
        assert "Mid-stream connection error" not in chunks[1]
        assert "done" in chunks[2]

    def test_stream_schema_cache_error_is_sanitized(self, client, mock_supabase, fake_chat, fake_chat_id, monkeypatch):
        chat_chain = MagicMock()
        chat_chain.execute.return_value = MagicMock(data=[fake_chat])

        repo_data = {
            "id": "some-repo",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "index_name": "some-index",
            "status": "ready",
        }
        repo_chain = MagicMock()
        repo_chain.execute.return_value = MagicMock(data=[repo_data])

        chats_table = MagicMock()
        chats_table.select.return_value.eq.return_value = chat_chain
        repos_table = MagicMock()
        repos_table.select.return_value.eq.return_value = repo_chain

        def mock_table(table_name):
            if table_name == "chats":
                return chats_table
            if table_name == "repositories":
                return repos_table
            return MagicMock()

        monkeypatch.setattr(mock_supabase, "table", mock_table)

        async def mock_stream(*args, **kwargs):
            yield 'data: {"type": "token", "content": "Start"}\n\n'
            raise RuntimeError("Could not find the table 'public.conversation_tags' in the schema cache")

        monkeypatch.setattr("api.routers.chat._get_stream_chat_response_callable", lambda: mock_stream)

        resp = client.post(
            f"/api/chat/{fake_chat_id}/message/stream",
            json={"query": "trigger schema cache error"},
        )
        assert resp.status_code == 200

        chunks = [(line.decode("utf-8") if isinstance(line, bytes) else line) for line in resp.iter_lines() if line]
        assert len(chunks) == 3  # token + error + done
        assert "error" in chunks[1]
        assert "repository memory issue" in chunks[1].lower()
        assert "conversation_tags" not in chunks[1]
        assert "done" in chunks[2]

