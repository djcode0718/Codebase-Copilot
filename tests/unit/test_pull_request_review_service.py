"""Smoke tests for api/services/pull_request_review_service.py"""
from __future__ import annotations
import pytest


def test_pull_request_review_service_module_importable():
    """Verify the pull_request_review_service module can be imported."""
    import api.services.pull_request_review_service as svc  # noqa: F401
    assert svc is not None
