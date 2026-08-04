"""Unit tests for chat_session_service orchestration helpers."""

import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.services import chat_session_service


def test_create_quick_ask_session_calls_create_chat(monkeypatch):
    expected = {"id": "c1", "session_type": "quick_ask"}

    def fake_create_chat(*args, **kwargs):
        assert kwargs["session_type"] == "quick_ask"
        return expected

    monkeypatch.setattr("api.services.supabase_service.create_chat", fake_create_chat)
    result = chat_session_service.create_quick_ask_session(MagicMock(), user_id="u1", repo_id="r1")
    assert result == expected


def test_get_or_create_main_session_returns_existing(monkeypatch):
    existing = {"id": "main-1"}
    monkeypatch.setattr("api.services.supabase_service.get_main_chat_for_repo", lambda *a, **k: existing)
    result = chat_session_service.get_or_create_main_session(MagicMock(), user_id="u1", repo_id="r1")
    assert result == existing


def test_update_session_flags_sets_title_and_archive(monkeypatch):
    captured = {}

    def fake_update(_supabase, _chat_id, fields):
        captured.update(fields)

    monkeypatch.setattr("api.services.supabase_service.update_chat_fields", fake_update)
    chat_session_service.update_session_flags(
        MagicMock(),
        "c1",
        title="  New title  ",
        is_pinned=True,
        is_favorite=False,
        is_archived=True,
    )
    assert captured["title"] == "New title"
    assert captured["is_pinned"] is True
    assert captured["is_favorite"] is False
    assert captured["is_archived"] is True
    assert "archived_at" in captured


def test_soft_delete_and_restore(monkeypatch):
    calls = []

    def fake_update(_supabase, _chat_id, fields):
        calls.append(fields)

    monkeypatch.setattr("api.services.supabase_service.update_chat_fields", fake_update)
    chat_session_service.soft_delete_session(MagicMock(), "c1")
    chat_session_service.restore_session(MagicMock(), "c1")

    assert calls[0]["deleted_at"] is not None
    assert calls[1]["deleted_at"] is None
    assert calls[1]["is_archived"] is False


