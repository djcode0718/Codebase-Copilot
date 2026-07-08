"""
tests/test_router_chat.py
──────────────────────────
Integration tests for the chat router endpoints:
  POST   /api/chat/session
  GET    /api/chat/list?repo_id=...
  GET    /api/chat/{chat_id}/messages
  DELETE /api/chat/{chat_id}

SSE streaming (/message/stream) is tested separately.
All external dependencies (Supabase, LLM) are mocked.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock


# ── POST /api/chat/session ────────────────────────────────────────────────────

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


# ── GET /api/chat/list ────────────────────────────────────────────────────────

class TestListChats:
    def test_lists_chats_for_repo(self, client, mock_supabase, fake_chat, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_chat])
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value = chain

        resp = client.get(f"/api/chat/list?repo_id={fake_repo_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert body[0]["id"] == fake_chat["id"]

    def test_returns_empty_list(self, client, mock_supabase, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value = chain

        resp = client.get(f"/api/chat/list?repo_id={fake_repo_id}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_missing_repo_id_returns_422(self, client):
        resp = client.get("/api/chat/list")
        assert resp.status_code == 422


# ── GET /api/chat/{chat_id}/messages ─────────────────────────────────────────

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


# ── DELETE /api/chat/{chat_id} ────────────────────────────────────────────────

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


# ── POST /api/chat/{chat_id}/message/stream ───────────────────────────────────

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
