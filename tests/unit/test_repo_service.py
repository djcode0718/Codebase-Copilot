"""Smoke test for app/services/repo_service.py"""
from __future__ import annotations
import pytest


def test_repo_service_module_importable():
    pytest.importorskip("git", reason="gitpython not installed in this environment")
    import app.services.repo_service as m  # noqa: F401
    assert m is not None
