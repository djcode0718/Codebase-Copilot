"""Unit tests for repository_knowledge_service ranking behavior."""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services.repository_knowledge_service import _score_text_match, get_repository_knowledge_context


def test_score_text_match_ignores_short_terms():
    assert _score_text_match("a an to", "anything") == 0


def test_score_text_match_counts_hits():
    score = _score_text_match("auth token middleware", "token checks in auth middleware")
    assert score >= 2


def test_get_repository_knowledge_context_filters_current_chat_and_sorts(monkeypatch):
    summaries = [
        {
            "chat_id": "c-current",
            "title": "Current",
            "executive_summary": "ignore me",
            "technical_summary": "",
            "keywords": ["auth"],
            "tags": ["security"],
        },
        {
            "chat_id": "c1",
            "title": "Auth review",
            "executive_summary": "auth token flow",
            "technical_summary": "",
            "keywords": ["authentication", "token"],
            "tags": ["security"],
        },
        {
            "chat_id": "c2",
            "title": "Caching",
            "executive_summary": "redis cache",
            "technical_summary": "",
            "keywords": ["cache"],
            "tags": ["performance"],
        },
    ]
    monkeypatch.setattr(
        "api.services.repository_knowledge_service.get_repo_conversation_summaries",
        lambda *_a, **_k: summaries,
    )
    monkeypatch.setattr(
        "api.services.repository_knowledge_service.get_repo_memory_messages",
        lambda *_a, **_k: [],
    )

    result = get_repository_knowledge_context(
        MagicMock(),
        user_id="u1",
        repo_id="r1",
        query="auth token",
        chat_id="c-current",
        max_items=2,
    )
    assert len(result) == 1
    assert result[0]["chat_id"] == "c1"


def test_get_repository_knowledge_context_backfills_from_messages(monkeypatch):
    monkeypatch.setattr(
        "api.services.repository_knowledge_service.get_repo_conversation_summaries",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(
        "api.services.repository_knowledge_service.get_repo_memory_messages",
        lambda *_a, **_k: [
            {"chat_id": "c9", "content": "Authentication middleware validates jwt token"},
            {"chat_id": "c8", "content": "Caching with redis"},
        ],
    )

    result = get_repository_knowledge_context(
        MagicMock(),
        user_id="u1",
        repo_id="r1",
        query="jwt token auth",
        chat_id="c-current",
        max_items=3,
    )

    assert len(result) == 1
    assert result[0]["chat_id"] == "c9"
    assert result[0]["anchor_type"] == "message"


