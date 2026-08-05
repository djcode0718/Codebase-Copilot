"""Smoke test for app/indexing/vector_store.py"""
from __future__ import annotations
import pytest


def test_vector_store_module_importable():
    pytest.importorskip("numpy", reason="numpy not installed in this environment")
    import app.indexing.vector_store as m  # noqa: F401
    assert m is not None
