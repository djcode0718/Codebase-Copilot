"""Unit tests for deterministic conversation summary extraction."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services.conversation_summary_service import build_conversation_summary


def test_build_summary_empty_messages():
    summary = build_conversation_summary([])
    assert summary["executive_summary"].startswith("No conversation")
    assert summary["files_discussed"] == []


def test_build_summary_extracts_entities_and_tags():
    messages = [
        {"role": "user", "content": "Please review api/routers/chat.py and AuthService for /api/chat/session risk."},
        {"role": "assistant", "content": "We should add JWT validation tests in tests/unit/test_dependencies.py."},
    ]
    summary = build_conversation_summary(messages)
    assert "api/routers/chat.py" in summary["files_discussed"]
    assert "AuthService" in summary["services_discussed"]
    assert any(tag for tag in summary["tags"] if tag == "conversation-memory")
    assert isinstance(summary["keywords"], list)

