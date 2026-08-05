"""Smoke test for app/llm/prompts.py"""
from __future__ import annotations


def test_prompts_module_importable():
    import app.llm.prompts as m  # noqa: F401
    assert m is not None
