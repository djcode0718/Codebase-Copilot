"""Smoke test for app/indexing/context_builder.py"""
from __future__ import annotations


def test_context_builder_module_importable():
    import app.indexing.context_builder as m  # noqa: F401
    assert m is not None
