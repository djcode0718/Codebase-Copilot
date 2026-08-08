"""Smoke test for app/indexing/file_map_builder.py"""
from __future__ import annotations
import pytest


def test_file_map_builder_module_importable():
    pytest.importorskip("numpy", reason="numpy not installed in this environment")
    import app.indexing.legacy.file_map_builder as m  # noqa: F401
    assert m is not None
