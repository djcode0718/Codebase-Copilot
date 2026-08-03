"""
tests/test_router_repo.py
──────────────────────────
Integration tests for the repository router endpoints:
  POST   /api/repo/index
  POST   /api/repo/{repo_id}/refresh
  GET    /api/repo/list
  GET    /api/repo/{repo_id}
  DELETE /api/repo/{repo_id}

Supabase and auth dependencies are fully mocked.
SSE /index-progress is tested separately (streaming).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock


# ── POST /api/repo/index ──────────────────────────────────────────────────────

class TestIndexRepository:
    def test_index_github_url_success(self, client, mock_supabase, fake_user_id, fake_repo_id):
        # Mock DB insert returning a repo record
        created_record = {
            "id": fake_repo_id,
            "name": "test-repo",
            "source_url": "https://github.com/example/test-repo",
            "index_name": "test-repo",
            "status": "indexing",
            "user_id": fake_user_id,
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[created_record])
        mock_supabase.table.return_value.insert.return_value = chain

        resp = client.post("/api/repo/index", json={"source": "https://github.com/example/test-repo"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["repo_id"] == fake_repo_id
        assert body["status"] == "indexing"
        assert body["index_name"] == "test-repo"

    def test_index_strips_dot_git_suffix(self, client, mock_supabase, fake_user_id, fake_repo_id):
        created_record = {
            "id": fake_repo_id,
            "name": "my-repo",
            "source_url": "https://github.com/x/my-repo.git",
            "index_name": "my-repo",
            "status": "indexing",
            "user_id": fake_user_id,
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[created_record])
        mock_supabase.table.return_value.insert.return_value = chain

        resp = client.post("/api/repo/index", json={"source": "https://github.com/x/my-repo.git"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["index_name"] == "my-repo"

    def test_index_local_path(self, client, mock_supabase, fake_user_id, fake_repo_id):
        created_record = {
            "id": fake_repo_id,
            "name": "myproject",
            "source_url": "/home/user/myproject",
            "index_name": "myproject",
            "status": "indexing",
            "user_id": fake_user_id,
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[created_record])
        mock_supabase.table.return_value.insert.return_value = chain

        resp = client.post("/api/repo/index", json={"source": "/home/user/myproject"})
        assert resp.status_code == 200

    def test_index_empty_source_returns_422(self, client):
        resp = client.post("/api/repo/index", json={"source": ""})
        assert resp.status_code == 422

    def test_index_missing_source_returns_422(self, client):
        resp = client.post("/api/repo/index", json={})
        assert resp.status_code == 422

    def test_index_whitespace_source_returns_422(self, client):
        resp = client.post("/api/repo/index", json={"source": "   "})
        assert resp.status_code == 422


# ── POST /api/repo/{repo_id}/refresh ────────────────────────────────────────

class TestRefreshRepository:
    def test_refresh_success(self, client, mock_supabase, fake_repo, fake_repo_id):
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = select_chain

        update_chain = MagicMock()
        update_chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.update.return_value.eq.return_value = update_chain

        with patch("os.path.exists", return_value=False):
            resp = client.post(f"/api/repo/{fake_repo_id}/refresh")

        assert resp.status_code == 200
        body = resp.json()
        assert body["repo_id"] == fake_repo_id
        assert body["status"] == "indexing"

    def test_refresh_404_if_not_found(self, client, mock_supabase, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(f"/api/repo/{fake_repo_id}/refresh")
        assert resp.status_code == 404

    def test_refresh_403_if_not_owner(self, client, mock_supabase, fake_repo_id):
        repo_other = {
            "id": fake_repo_id,
            "user_id": "other-user",
            "name": "test",
            "source_url": "https://github.com/x/y",
            "index_name": "y",
            "status": "ready",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[repo_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(f"/api/repo/{fake_repo_id}/refresh")
        assert resp.status_code == 403


# ── GET /api/repo/list ────────────────────────────────────────────────────────

class TestListRepositories:
    def test_returns_list(self, client, mock_supabase, fake_user_id, fake_repo):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value = chain

        resp = client.get("/api/repo/list")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["id"] == fake_repo["id"]

    def test_returns_empty_list(self, client, mock_supabase):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value = chain

        resp = client.get("/api/repo/list")
        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /api/repo/{repo_id} ───────────────────────────────────────────────────

class TestGetRepository:
    def test_returns_repo(self, client, mock_supabase, fake_repo, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get(f"/api/repo/{fake_repo_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == fake_repo_id
        assert body["status"] == "ready"

    def test_returns_404_if_not_found(self, client, mock_supabase):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get("/api/repo/nonexistent-id")
        assert resp.status_code == 404

    def test_returns_403_if_not_owner(self, client, mock_supabase, fake_repo_id):
        repo_other_user = {
            "id": fake_repo_id,
            "user_id": "other-user-id",
            "name": "test",
            "source_url": "https://github.com/x/y",
            "index_name": "y",
            "status": "ready",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[repo_other_user])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get(f"/api/repo/{fake_repo_id}")
        assert resp.status_code == 403


# ── DELETE /api/repo/{repo_id} ────────────────────────────────────────────────

class TestDeleteRepository:
    def test_deletes_successfully(self, client, mock_supabase, fake_repo, fake_repo_id):
        # GET repo
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = select_chain

        # DELETE repo
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.delete.return_value.eq.return_value = delete_chain

        with patch("os.path.exists", return_value=False):
            resp = client.delete(f"/api/repo/{fake_repo_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert "deleted" in body["message"].lower() or "test-repo" in body["message"]

    def test_delete_404_if_not_found(self, client, mock_supabase):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.delete("/api/repo/nonexistent")
        assert resp.status_code == 404

    def test_delete_403_if_not_owner(self, client, mock_supabase, fake_repo_id):
        repo_other = {
            "id": fake_repo_id,
            "user_id": "other-user",
            "name": "test",
            "source_url": "https://github.com/x/y",
            "index_name": "y",
            "status": "ready",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[repo_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.delete(f"/api/repo/{fake_repo_id}")
        assert resp.status_code == 403

    def test_delete_removes_directories(self, client, mock_supabase, fake_repo, fake_repo_id):
        # GET repo
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = select_chain

        # DELETE
        delete_chain = MagicMock()
        delete_chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.delete.return_value.eq.return_value = delete_chain

        with (
            patch("os.path.exists", return_value=True),
            patch("shutil.rmtree") as mock_rmtree,
        ):
            resp = client.delete(f"/api/repo/{fake_repo_id}")

        assert resp.status_code == 200
        # shutil.rmtree should have been called for index and repo dirs
        assert mock_rmtree.call_count == 2
