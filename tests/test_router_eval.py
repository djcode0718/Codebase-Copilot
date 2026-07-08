"""
tests/test_router_eval.py
──────────────────────────
Tests for evaluation router endpoints:
  POST /api/eval/run          (SSE — checks auth/access guards)
  GET  /api/eval/{repo_id}/latest
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock


# ── GET /api/eval/{repo_id}/latest ───────────────────────────────────────────

class TestGetLatestEvaluation:
    def test_returns_eval_data(self, client, mock_supabase, fake_repo, fake_repo_id):
        eval_record = {
            "id": "eval-001",
            "repo_id": fake_repo_id,
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
            "result_json": {"total_queries": 10},
            "created_at": "2025-01-01T00:00:00+00:00",
        }

        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "repositories":
                eq_chain = MagicMock()
                eq_chain.execute.return_value = MagicMock(data=[fake_repo])
                mock_table.select.return_value.eq.return_value = eq_chain
            elif table_name == "evaluations":
                limit_chain = MagicMock()
                limit_chain.execute.return_value = MagicMock(data=[eval_record])
                mock_table.select.return_value.eq.return_value.order.return_value.limit.return_value = limit_chain
            return mock_table

        mock_supabase.table.side_effect = table_side_effect

        resp = client.get(f"/api/eval/{fake_repo_id}/latest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["hit_rate"] == 0.9
        assert body["total_queries"] == 10
        assert body["colbert_enabled"] is False

    def test_returns_none_if_no_eval(self, client, mock_supabase, fake_repo, fake_repo_id):
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "repositories":
                eq_chain = MagicMock()
                eq_chain.execute.return_value = MagicMock(data=[fake_repo])
                mock_table.select.return_value.eq.return_value = eq_chain
            elif table_name == "evaluations":
                limit_chain = MagicMock()
                limit_chain.execute.return_value = MagicMock(data=[])
                mock_table.select.return_value.eq.return_value.order.return_value.limit.return_value = limit_chain
            return mock_table

        mock_supabase.table.side_effect = table_side_effect

        resp = client.get(f"/api/eval/{fake_repo_id}/latest")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_returns_404_if_repo_not_found(self, client, mock_supabase, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get(f"/api/eval/{fake_repo_id}/latest")
        assert resp.status_code == 404

    def test_returns_403_if_not_owner(self, client, mock_supabase, fake_repo_id):
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

        resp = client.get(f"/api/eval/{fake_repo_id}/latest")
        assert resp.status_code == 403


# ── POST /api/eval/run ───────────────────────────────────────────────────────

class TestRunEvaluation:
    """
    The /api/eval/run endpoint streams SSE and runs a heavy evaluation pipeline.
    We test the access-control guards here (404, 403).
    Full pipeline testing is covered in the evaluate.py unit tests.
    """

    def test_returns_404_if_repo_not_found(self, client, mock_supabase):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(
            "/api/eval/run",
            json={"repo_id": "bad-repo-id", "index_name": "bad-repo"},
        )
        assert resp.status_code == 404

    def test_returns_403_if_not_owner(self, client, mock_supabase):
        repo_other = {
            "id": "some-repo",
            "user_id": "other-user",
            "status": "ready",
            "name": "test",
            "source_url": "https://github.com/x/y",
            "index_name": "y",
        }
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[repo_other])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.post(
            "/api/eval/run",
            json={"repo_id": "some-repo", "index_name": "y"},
        )
        assert resp.status_code == 403

    def test_missing_body_fields_returns_422(self, client):
        resp = client.post("/api/eval/run", json={"repo_id": "r1"})  # missing index_name
        assert resp.status_code == 422

    def test_empty_body_returns_422(self, client):
        resp = client.post("/api/eval/run", json={})
        assert resp.status_code == 422
