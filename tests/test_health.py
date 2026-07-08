"""
tests/test_health.py
─────────────────────
Tests for GET /api/health endpoint.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture()
def client_for_health():
    """
    Minimal TestClient that patches:
      - configure_llamaindex_settings (startup event)
      - LlamaIndex Settings object (health check)
      - app.config (LLM_PROVIDER etc.)
    """
    mock_settings = MagicMock()
    mock_settings.embed_model = MagicMock()
    mock_settings.embed_model.__class__ = type("OllamaEmbedding", (), {})

    with (
        patch("app.llm.llm_client.configure_llamaindex_settings"),
        patch("api.routers.repo.__init__", create=True),
        patch("llama_index.core.Settings", mock_settings),
    ):
        from api.main import app
        with TestClient(app) as c:
            yield c


class TestHealth:
    """Tests for the /api/health endpoint."""

    def test_health_returns_200(self, client):
        with (
            patch("llama_index.core.Settings") as mock_s,
            patch("app.config.LLM_PROVIDER", "groq"),
            patch("app.config.USE_FAST_LLM", False),
            patch("app.config.USE_COLBERT", False),
        ):
            mock_s.embed_model = MagicMock()
            type(mock_s.embed_model).__name__ = "OllamaEmbedding"
            resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_response_shape(self, client):
        with (
            patch("llama_index.core.Settings") as mock_s,
            patch("app.config.LLM_PROVIDER", "groq"),
            patch("app.config.USE_FAST_LLM", False),
            patch("app.config.USE_COLBERT", False),
        ):
            mock_s.embed_model = None
            resp = client.get("/api/health")

        body = resp.json()
        assert "status" in body
        assert body["status"] == "ok"
        assert "llm_provider" in body

    def test_health_embed_model_field_present(self, client):
        with (
            patch("llama_index.core.Settings") as mock_s,
            patch("app.config.LLM_PROVIDER", "groq"),
            patch("app.config.USE_FAST_LLM", False),
            patch("app.config.USE_COLBERT", False),
        ):
            mock_s.embed_model = None
            resp = client.get("/api/health")

        body = resp.json()
        assert "embed_model" in body
