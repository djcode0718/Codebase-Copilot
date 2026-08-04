"""
tests/test_router_suggestions.py
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Tests for the suggestions router:
  GET /api/repo/{repo_id}/suggestions

Tests cover:
  - Cache hit (returns cached questions)
  - Repo not found (404)
  - Repo owned by other user (403)
  - Repo not ready â†’ returns default suggestions
  - Context doc not found â†’ returns default suggestions
  - LLM generates questions â†’ returns generated suggestions
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

import api.routers.suggestions as suggestions_module


@pytest.fixture(autouse=True)
def clear_suggestions_cache():
    """Clear the in-process suggestions cache before each test."""
    suggestions_module._suggestions_cache.clear()
    yield
    suggestions_module._suggestions_cache.clear()


class TestGetSuggestions:
    def test_returns_cached_questions(self, client, fake_repo_id):
        """If questions are already cached, they're returned immediately."""
        cached = ["What is this?", "How does X work?", "Explain Y?"]
        suggestions_module._suggestions_cache[fake_repo_id] = cached

        resp = client.get(f"/api/repo/{fake_repo_id}/suggestions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["questions"] == cached

    def test_returns_404_if_repo_not_found(self, client, mock_supabase, fake_repo_id):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        resp = client.get(f"/api/repo/{fake_repo_id}/suggestions")
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

        resp = client.get(f"/api/repo/{fake_repo_id}/suggestions")
        assert resp.status_code == 403

    def test_returns_defaults_if_repo_not_ready(
        self, client, mock_supabase, fake_user_id, fake_repo_id
    ):
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

        resp = client.get(f"/api/repo/{fake_repo_id}/suggestions")
        assert resp.status_code == 200
        body = resp.json()
        assert "questions" in body
        assert len(body["questions"]) == 6

    def test_returns_defaults_if_no_context_doc(
        self, client, mock_supabase, fake_user_id, fake_repo_id, fake_repo
    ):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        with patch.object(suggestions_module, "_load_context_doc", return_value=None):
            resp = client.get(f"/api/repo/{fake_repo_id}/suggestions")

        assert resp.status_code == 200
        body = resp.json()
        assert "questions" in body
        assert len(body["questions"]) == 6

    def test_generates_questions_from_context(
        self, client, mock_supabase, fake_user_id, fake_repo_id, fake_repo
    ):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        generated_questions = [
            "How does the indexing pipeline work?",
            "What retrieval strategy is used?",
            "How is the LLM integrated?",
            "What does chat_service.py do?",
            "How is Supabase used for storage?",
            "What is the purpose of evaluate.py?",
        ]

        with (
            patch.object(suggestions_module, "_load_context_doc", return_value="...context..."),
            patch.object(
                suggestions_module,
                "_generate_suggestions",
                new=AsyncMock(return_value=generated_questions),
            ),
        ):
            resp = client.get(f"/api/repo/{fake_repo_id}/suggestions")

        assert resp.status_code == 200
        body = resp.json()
        assert body["questions"] == generated_questions
        # Should now be cached
        assert suggestions_module._suggestions_cache.get(fake_repo_id) == generated_questions

    def test_questions_are_cached_after_first_request(
        self, client, mock_supabase, fake_user_id, fake_repo_id, fake_repo
    ):
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=[fake_repo])
        mock_supabase.table.return_value.select.return_value.eq.return_value = chain

        with (
            patch.object(suggestions_module, "_load_context_doc", return_value=None),
        ):
            resp1 = client.get(f"/api/repo/{fake_repo_id}/suggestions")
            resp2 = client.get(f"/api/repo/{fake_repo_id}/suggestions")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Both should return same default list
        assert resp1.json()["questions"] == resp2.json()["questions"]


# â”€â”€ _default_suggestions unit test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestDefaultSuggestions:
    def test_returns_exactly_6_questions(self):
        questions = suggestions_module._default_suggestions()
        assert len(questions) == 6
        assert all(isinstance(q, str) for q in questions)
        assert all(len(q) > 0 for q in questions)


# â”€â”€ _load_context_doc unit test â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestLoadContextDoc:
    def test_returns_none_if_file_missing(self):
        with patch("os.path.exists", return_value=False):
            result = suggestions_module._load_context_doc("nonexistent-index")
        assert result is None

    def test_returns_file_content(self, tmp_path):
        index_name = "my-index"
        context_dir = tmp_path / index_name
        context_dir.mkdir()
        context_file = context_dir / "codebase_context.txt"
        context_file.write_text("This is the codebase context.")

        with patch("api.routers.suggestions.INDEX_DIR", str(tmp_path)):
            result = suggestions_module._load_context_doc(index_name)

        assert result == "This is the codebase context."

