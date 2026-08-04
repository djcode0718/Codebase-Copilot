"""Unit tests for chat_search_service."""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services.chat_search_service import _snippet, search_repository_conversations


def test_snippet_handles_empty_text():
    assert _snippet("", "auth") == ""


def test_snippet_returns_context_around_match():
    text = "prefix " + ("x" * 40) + " authentication middleware " + ("y" * 40)
    result = _snippet(text, "authentication", radius=20)
    assert "authentication" in result.lower()
    assert len(result) <= len(text)


def test_search_repository_conversations_combines_sources(monkeypatch):
    monkeypatch.setattr(
        "api.services.supabase_service.search_chats",
        lambda *_a, **_k: [{"id": "c1", "title": "Auth investigation"}],
    )
    monkeypatch.setattr(
        "api.services.supabase_service.search_messages_in_chat",
        lambda *_a, **_k: [{"id": "m1", "content": "JWT validation path"}],
    )
    monkeypatch.setattr(
        "api.services.supabase_service.get_conversation_summary",
        lambda *_a, **_k: {"executive_summary": "Authentication flow and token checks"},
    )

    results = search_repository_conversations(
        MagicMock(),
        user_id="u1",
        repo_id="r1",
        query="auth",
        limit=20,
        offset=0,
    )

    assert len(results) == 1
    assert results[0]["chat"]["id"] == "c1"
    assert results[0]["matched_messages"][0]["id"] == "m1"
    assert len(results[0]["snippets"]) >= 1

