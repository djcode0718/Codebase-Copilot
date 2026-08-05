"""Smoke tests for api/services/repository_memory_service.py"""
from __future__ import annotations
import pytest


def test_repository_memory_service_module_importable():
    """Verify the repository_memory_service module can be imported."""
    import api.services.repository_memory_service as svc  # noqa: F401
    assert svc is not None
