"""Smoke test for app/retrieval/file_map_retriever.py"""
from __future__ import annotations
import pytest


def test_file_map_retriever_module_importable():
    pytest.importorskip("numpy", reason="numpy not installed in this environment")
    import app.retrieval.legacy.file_map_retriever as m  # noqa: F401
    assert m is not None
