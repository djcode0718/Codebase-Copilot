"""Smoke test for app/retrieval/ranking.py"""
from __future__ import annotations


def test_ranking_module_importable():
    import app.retrieval.legacy.ranking as m  # noqa: F401
    assert m is not None
