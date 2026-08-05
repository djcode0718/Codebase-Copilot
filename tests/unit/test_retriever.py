"""Smoke test for app/retrieval/retriever.py"""
from __future__ import annotations
import pytest


def test_retriever_module_importable():
    pytest.importorskip("numpy", reason="numpy not installed in this environment")
    import app.retrieval.retriever as m  # noqa: F401
    assert m is not None
