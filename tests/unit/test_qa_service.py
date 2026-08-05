"""Smoke test for app/services/qa_service.py"""
from __future__ import annotations


def test_qa_service_module_importable():
    import app.services.qa_service as m  # noqa: F401
    assert m is not None
