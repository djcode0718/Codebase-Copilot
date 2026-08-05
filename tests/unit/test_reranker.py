"""Smoke test for app/retrieval/reranker.py"""
from __future__ import annotations


def test_reranker_module_importable():
    import app.retrieval.reranker as m  # noqa: F401
    assert m is not None
