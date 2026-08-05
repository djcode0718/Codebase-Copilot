"""Smoke tests for app/utils/helpers.py and app/utils/logger.py"""
from __future__ import annotations


def test_helpers_module_importable():
    import app.utils.helpers as m  # noqa: F401
    assert m is not None


def test_logger_module_importable():
    import app.utils.logger as m  # noqa: F401
    assert m is not None
