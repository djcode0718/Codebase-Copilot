"""
tests/test_router_repo.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import patch, MagicMock


# â”€â”€ POST /api/repo/index â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    def test_index_sanitizes_name_from_url_with_query(self, client, mock_supabase, fake_user_id, fake_repo_id):
        created_record = {
            "id": fake_repo_id,
            "name": "my-repo",
            "source_url": "https://github.com/x/my-repo.git?ref=main",
            "index_name": "my-repo",
            "status": "indexing",
            "user_id": fake_user_id,
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[created_record])
        mock_supabase.table.return_value.insert.return_value = chain

        resp = client.post("/api/repo/index", json={"source": "https://github.com/x/my-repo.git?ref=main"})

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


# â”€â”€ POST /api/repo/{repo_id}/refresh â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ GET /api/repo/list â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ GET /api/repo/{repo_id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ DELETE /api/repo/{repo_id} â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


class TestBranchWorkspace:
    def test_list_branches_success(self, client, mock_supabase, fake_repo, fake_repo_id):
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = select_chain

        with patch("api.routers.repo.repo_branch_service.list_branches", return_value={
            "current_branch": "feature/payment",
            "default_branch": "main",
            "recent_branches": ["feature/payment", "main"],
            "local_branches": ["main", "feature/payment"],
            "remote_branches": ["main", "feature/payment"],
        }):
            resp = client.get(f"/api/repo/{fake_repo_id}/branches?query=feature")

        assert resp.status_code == 200
        body = resp.json()
        assert body["current_branch"] == "feature/payment"
        assert "feature/payment" in body["local_branches"]

    def test_get_branch_status_success(self, client, mock_supabase, fake_repo, fake_repo_id):
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = select_chain

        payload = {
            "current_branch": "main",
            "default_branch": "main",
            "last_commit": "Initial commit",
            "author": "Dev",
            "commit_sha": "abc123def456",
            "short_commit_sha": "abc123def456",
            "ahead": 0,
            "behind": 0,
            "changed_files": 0,
            "changed_paths": [],
            "captured_at": "2026-08-07T00:00:00Z",
            "indexed_at": None,
            "index_status": "ready",
            "evaluation_status": "ready",
            "health_score": 95,
        }

        with (
            patch("api.routers.repo.repo_branch_service.get_branch_status", return_value=payload),
            patch("api.routers.repo._enrich_branch_status_with_repo_metrics", return_value=payload),
        ):
            resp = client.get(f"/api/repo/{fake_repo_id}/branches/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["current_branch"] == "main"
        assert body["health_score"] == 95

    def test_compare_branches_success(self, client, mock_supabase, fake_repo, fake_repo_id):
        select_chain = MagicMock()
        select_chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = select_chain

        compare_payload = {
            "base_branch": "main",
            "target_branch": "feature/payment",
            "changed_files": 5,
            "sample_changed_files": ["api/routers/repo.py"],
            "architecture_changes": 1,
            "security_changes": 0,
            "performance_changes": 1,
            "technical_debt_changes": 0,
            "api_changes": 1,
            "database_changes": 0,
            "business_logic_changes": 1,
            "dependency_changes": 0,
            "testing_changes": 1,
            "health_impact_delta": -2,
            "security_impact_delta": 0,
            "test_impact_delta": 1,
            "impact_summary": "Estimated health delta -2; security delta 0; test coverage delta +1.",
            "risk_assessment": "Low",
            "merge_readiness": {
                "overall_score": 92,
                "blocking_issues": [],
                "warnings": [],
                "suggested_reviewers": ["Backend Lead"],
                "estimated_review_time_minutes": 40,
                "deployment_risk": "Low",
                "safe_to_merge": True,
            },
            "ai_executive_summary": "Ready to merge.",
        }

        with patch("api.routers.repo.repo_branch_service.compare_branches", return_value=compare_payload):
            resp = client.get(f"/api/repo/{fake_repo_id}/branches/compare?base_branch=main&target_branch=feature/payment")

        assert resp.status_code == 200
        body = resp.json()
        assert body["base_branch"] == "main"
        assert body["merge_readiness"]["safe_to_merge"] is True


