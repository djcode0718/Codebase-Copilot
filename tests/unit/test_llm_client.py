"""Smoke test for app/llm/llm_client.py"""
from __future__ import annotations
import pytest


def test_llm_client_module_importable():
    # Skip if llama_index is not installed
    pytest.importorskip("llama_index", reason="llama_index not installed in this environment")
    from app.llm import llm_client as m  # noqa: F401
    assert m is not None
