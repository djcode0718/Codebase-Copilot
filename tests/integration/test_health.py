"""
tests/test_health.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Tests for GET /api/health endpoint.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import patch


class TestHealth:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client):
        with (
            patch("app.config.LLM_PROVIDER", "groq"),
            patch("app.config.USE_FAST_LLM", False),
            patch("app.config.USE_RERANKER", False),
        ):
            resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_response_shape(self, client):
        with (
            patch("app.config.LLM_PROVIDER", "groq"),
            patch("app.config.USE_FAST_LLM", False),
            patch("app.config.USE_RERANKER", False),
        ):
            resp = client.get("/api/health")

        body = resp.json()
        assert "status" in body
        assert body["status"] == "ok"
        assert "llm_provider" in body

    def test_health_embed_model_field_present(self, client):
        with (
            patch("app.config.LLM_PROVIDER", "groq"),
            patch("app.config.USE_FAST_LLM", False),
            patch("app.config.USE_RERANKER", False),
        ):
            resp = client.get("/api/health")

        body = resp.json()
        assert "embed_model" in body

