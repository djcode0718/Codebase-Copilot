"""Smoke test for app/parsing/chunk_utils.py"""
from __future__ import annotations


def test_chunk_utils_module_importable():
    import app.parsing.chunk_utils as m  # noqa: F401
    assert m is not None
