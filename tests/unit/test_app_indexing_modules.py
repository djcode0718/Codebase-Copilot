"""Smoke tests for app/indexing modules: context_builder, file_map_builder, index_builder, vector_store"""
from __future__ import annotations
import pytest


def test_context_builder_importable():
    import app.indexing.context_builder as m  # noqa: F401
    assert m is not None


def test_file_map_builder_importable():
    pytest.importorskip("numpy", reason="numpy not installed")
    import app.indexing.legacy.file_map_builder as m  # noqa: F401
    assert m is not None


def test_index_builder_importable():
    pytest.importorskip("chromadb", reason="chromadb not installed")
    import app.indexing.index_builder as m  # noqa: F401
    assert m is not None


def test_vector_store_importable():
    pytest.importorskip("numpy", reason="numpy not installed")
    import app.indexing.legacy.vector_store as m  # noqa: F401
    assert m is not None

