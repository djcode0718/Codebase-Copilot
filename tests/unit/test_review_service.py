"""Smoke tests for api/services/review_service.py, review_storage_service.py, review_suggestion_service.py"""
from __future__ import annotations
import pytest


def test_review_service_module_importable():
    import api.services.review_service as svc  # noqa: F401
    assert svc is not None


def test_review_storage_service_module_importable():
    import api.services.review_storage_service as svc  # noqa: F401
    assert svc is not None


def test_review_suggestion_service_module_importable():
    import api.services.review_suggestion_service as svc  # noqa: F401
    assert svc is not None
