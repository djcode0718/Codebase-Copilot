"""Smoke test for app/indexing/index_builder.py"""
from __future__ import annotations
import pytest


def test_index_builder_module_importable():
    pytest.importorskip("chromadb", reason="chromadb not installed in this environment")
    import app.indexing.index_builder as m  # noqa: F401
    assert m is not None
