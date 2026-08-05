"""Smoke test for app/services/model_manager.py"""
from __future__ import annotations


def test_model_manager_module_importable():
    import app.services.model_manager as m  # noqa: F401
    assert m is not None
