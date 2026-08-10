"""
tests/integration/test_router_graph.py
──────────────────────────────────────
Integration tests for the relationship graph router endpoints:
  GET /api/repo/{repo_id}/relationship-graph
  GET /api/repo/{repo_id}/relationship-graph/keys
"""

import json
import os
import shutil
import pytest
from unittest.mock import MagicMock

# The conftest sets INDEX_DIR to /tmp/test_indices
TEST_INDEX_DIR = "/tmp/test_indices"

@pytest.fixture(autouse=True)
def setup_clean_test_index_dir():
    """Ensure index dir is clean before and after each test."""
    if os.path.exists(TEST_INDEX_DIR):
        shutil.rmtree(TEST_INDEX_DIR)
    os.makedirs(TEST_INDEX_DIR, exist_ok=True)
    yield
    if os.path.exists(TEST_INDEX_DIR):
        shutil.rmtree(TEST_INDEX_DIR)


class TestRelationshipGraphEndpoints:
    def _setup_repo_mock(self, mock_supabase, fake_repo):
        """Wire mock to return fake_repo on get_repo."""
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_repo] if fake_repo else [])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

    def test_get_graph_success(self, client, mock_supabase, fake_repo, fake_repo_id, auth_headers):
        # Setup repo mock
        self._setup_repo_mock(mock_supabase, fake_repo)

        # Create relationship_graph.json on disk
        index_name = fake_repo["index_name"]
        repo_index_dir = os.path.join(TEST_INDEX_DIR, index_name)
        os.makedirs(repo_index_dir, exist_ok=True)
        
        graph_data = {
            "my_module.func_a": ["file_b.py", "file_c.py"],
            "ClassB": ["file_a.py"]
        }
        with open(os.path.join(repo_index_dir, "relationship_graph.json"), "w", encoding="utf-8") as f:
            json.dump(graph_data, f)

        # Request graph
        resp = client.get(f"/api/repo/{fake_repo_id}/relationship-graph", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "graph" in body
        assert body["graph"] == graph_data

    def test_get_graph_keys_success(self, client, mock_supabase, fake_repo, fake_repo_id, auth_headers):
        # Setup repo mock
        self._setup_repo_mock(mock_supabase, fake_repo)

        # Create relationship_graph.json on disk
        index_name = fake_repo["index_name"]
        repo_index_dir = os.path.join(TEST_INDEX_DIR, index_name)
        os.makedirs(repo_index_dir, exist_ok=True)
        
        graph_data = {
            "my_module.func_a": ["file_b.py", "file_c.py"],
            "ClassB": ["file_a.py"]
        }
        with open(os.path.join(repo_index_dir, "relationship_graph.json"), "w", encoding="utf-8") as f:
            json.dump(graph_data, f)

        # Request graph keys
        resp = client.get(f"/api/repo/{fake_repo_id}/relationship-graph/keys", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "keys" in body
        assert set(body["keys"]) == {"my_module.func_a", "ClassB"}

    def test_fails_if_repo_not_found(self, client, mock_supabase, fake_repo_id, auth_headers):
        # Mock empty database response
        self._setup_repo_mock(mock_supabase, None)

        resp = client.get(f"/api/repo/{fake_repo_id}/relationship-graph", headers=auth_headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_fails_if_repo_owned_by_other(self, client, mock_supabase, fake_repo, fake_repo_id, auth_headers):
        # Repo owned by someone else
        fake_repo["user_id"] = "other-user"
        self._setup_repo_mock(mock_supabase, fake_repo)

        resp = client.get(f"/api/repo/{fake_repo_id}/relationship-graph", headers=auth_headers)
        assert resp.status_code == 403
        assert "denied" in resp.json()["detail"].lower()

    def test_fails_if_graph_file_missing(self, client, mock_supabase, fake_repo, fake_repo_id, auth_headers):
        # Setup repo mock
        self._setup_repo_mock(mock_supabase, fake_repo)

        # Ensure index dir is clean (no graph json)
        index_name = fake_repo["index_name"]
        repo_index_dir = os.path.join(TEST_INDEX_DIR, index_name)
        if os.path.exists(repo_index_dir):
            shutil.rmtree(repo_index_dir)

        resp = client.get(f"/api/repo/{fake_repo_id}/relationship-graph", headers=auth_headers)
        assert resp.status_code == 404
        assert "relationship graph not found" in resp.json()["detail"].lower()
