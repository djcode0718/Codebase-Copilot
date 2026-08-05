"""Smoke tests for review_storage_service.py (additional coverage)"""
from __future__ import annotations


def test_review_storage_service_importable():
    import api.services.review_storage_service as svc  # noqa: F401
    assert svc is not None
