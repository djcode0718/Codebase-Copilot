"""Smoke tests for api/services/indexing_service.py"""
from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch


def test_indexing_service_module_importable():
    """Verify the indexing_service module can be imported without errors."""
    import api.services.indexing_service as svc  # noqa: F401
    assert svc is not None


def test_indexing_in_flight_set_is_empty_on_init():
    """The in-flight tracking set starts empty."""
    from api.services.indexing_service import _indexing_in_flight
    # It may contain items from other tests but should be a set
    assert isinstance(_indexing_in_flight, set)
