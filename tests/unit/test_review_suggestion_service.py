"""Smoke tests for review_suggestion_service.py (additional coverage)"""
from __future__ import annotations


def test_review_suggestion_service_importable():
    import api.services.review_suggestion_service as svc  # noqa: F401
    assert svc is not None
