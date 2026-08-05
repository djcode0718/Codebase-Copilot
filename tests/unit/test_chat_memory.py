"""Smoke test for app/memory/chat_memory.py"""
from __future__ import annotations


def test_chat_memory_module_importable():
    import app.memory.chat_memory as m  # noqa: F401
    assert m is not None
