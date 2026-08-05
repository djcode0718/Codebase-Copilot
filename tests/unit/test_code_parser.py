"""Smoke test for app/parsing/code_parser.py"""
from __future__ import annotations
import pytest


def test_code_parser_module_importable():
    pytest.importorskip("tqdm", reason="tqdm not installed in this environment")
    import app.parsing.code_parser as m  # noqa: F401
    assert m is not None
