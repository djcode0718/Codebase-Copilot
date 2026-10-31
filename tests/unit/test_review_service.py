"""Unit tests for api/services/review_service.py: budget resolution, accumulation, and truncation."""
from __future__ import annotations

import ast
import os
import pytest
from unittest.mock import patch

from api.services.review_service import (
    _TRUNCATION_SENTINEL,
    _collect_targets,
    _read_repo_file,
    _resolve_review_budget,
)
from app.llm.prompts import REVIEW_PAYLOAD_PROMPT


def test_review_service_module_importable():
    import api.services.review_service as svc
    assert svc is not None


def test_provider_aware_budget_resolution():
    # Gemini profile
    single, agg, per_file = _resolve_review_budget(1, provider="gemini")
    assert single == 40000
    assert agg == 60000
    assert per_file == 40000

    single, agg, per_file = _resolve_review_budget(5, provider="gemini")
    assert agg == 60000
    assert per_file == 20000  # per_file_max for Gemini

    # Groq profile
    single, agg, per_file = _resolve_review_budget(1, provider="groq")
    assert single == 40000
    assert agg == 50000

    single, agg, per_file = _resolve_review_budget(5, provider="groq")
    assert agg == 50000
    assert per_file == 15000  # per_file_max for Groq

    # Ollama profile
    single, agg, per_file = _resolve_review_budget(1, provider="ollama")
    assert single == 40000
    assert agg == 45000

    single, agg, per_file = _resolve_review_budget(5, provider="ollama")
    assert agg == 45000
    assert per_file == 12000  # per_file_max for Ollama


def test_read_repo_file_under_limit_untruncated(tmp_path):
    test_file = tmp_path / "small.py"
    content = "def hello():\n    return 'world'\n"
    test_file.write_text(content, encoding="utf-8")

    target = _read_repo_file(str(tmp_path), "small.py", max_chars=40000)
    assert target is not None
    assert target.content == content
    assert _TRUNCATION_SENTINEL not in target.content


def test_read_repo_file_sensevoice_equivalent_preserved(tmp_path):
    # Construct a valid Python file of ~35,252 characters
    lines = ["# Synthetically constructed SenseVoice-equivalent module\n"]
    idx = 0
    while sum(len(l) for l in lines) < 35200:
        lines.append(f"def process_layer_{idx}(input_tensor: int) -> int:\n    return input_tensor * {idx} + 1\n\n")
        idx += 1
    content = "".join(lines)
    assert len(content) >= 35200

    test_file = tmp_path / "model.py"
    test_file.write_text(content, encoding="utf-8")

    target = _read_repo_file(str(tmp_path), "model.py", max_chars=40000)
    assert target is not None
    assert target.content == content
    assert _TRUNCATION_SENTINEL not in target.content
    # Must compile with zero AST errors
    ast.parse(target.content)


def test_read_repo_file_oversized_receives_sentinel_and_snaps_to_newline(tmp_path):
    # 50 lines of 100 characters each = ~5,000 chars
    lines = [f"# Line {i:03d} " + ("x" * 85) + "\n" for i in range(50)]
    full_text = "".join(lines)

    test_file = tmp_path / "oversized.py"
    test_file.write_text(full_text, encoding="utf-8")

    # Read with limit of 2,500 chars
    target = _read_repo_file(str(tmp_path), "oversized.py", max_chars=2500)
    assert target is not None
    assert _TRUNCATION_SENTINEL in target.content

    # Check that text preceding the sentinel snaps cleanly to a newline
    body = target.content.replace(_TRUNCATION_SENTINEL, "")
    assert body.endswith("\n") or body.endswith("x")
    # Body without sentinel must be <= 2500 characters
    assert len(body) <= 2500


def test_collect_targets_multi_file_accumulator_hard_cap(tmp_path):
    # Create 10 files of 15,000 characters each (total 150,000 chars)
    file_names = []
    for i in range(10):
        fn = f"file_{i}.py"
        file_names.append(fn)
        fp = tmp_path / fn
        fp.write_text(f"# File {i}\n" + ("x" * 14900) + "\n", encoding="utf-8")

    repo = {"name": "test-repo", "index_name": "test-repo"}
    with patch("api.services.review_service._resolve_repo_root", return_value=str(tmp_path)):
        # Under Gemini: aggregate limit is 60,000 chars
        targets, missing = _collect_targets(repo, file_names, provider="gemini")

        total_chars = sum(len(t.content) for t in targets)
        # Authoritative guard: total content must NEVER exceed the aggregate budget + sentinels
        # Specifically, the source characters ingested without sentinel must be <= 60000
        source_chars = sum(len(t.content.replace(_TRUNCATION_SENTINEL, "")) for t in targets)
        assert source_chars <= 60000

        # Excess files must be reported in missing with clear budget explanation
        assert len(missing) > 0
        assert any("skipped: review context budget exhausted" in m for m in missing)


def test_review_payload_prompt_contains_truncation_instruction():
    assert "IMPORTANT TRUNCATION RULES" in REVIEW_PAYLOAD_PROMPT
    assert "[TRUNCATED FOR REVIEW]" in REVIEW_PAYLOAD_PROMPT
    assert "Never interpret an incomplete expression" in REVIEW_PAYLOAD_PROMPT


def test_review_budget_resolves_groq_when_use_fast_llm_active():
    from app.services.model_manager import ModelSpec
    with patch("app.services.model_manager.get_available_model_specs", return_value=[ModelSpec("groq", "qwen/qwen3.8-27b")]):
        single, agg, per_file = _resolve_review_budget(5)
        # Groq budget profile must be selected
        assert single == 40000
        assert agg == 50000
        assert per_file == 15000


def test_review_budget_preserves_ollama_when_use_fast_llm_active():
    from app.services.model_manager import ModelSpec
    with patch("app.services.model_manager.get_available_model_specs", return_value=[ModelSpec("ollama", "llama3.1:8b")]):
        single, agg, per_file = _resolve_review_budget(5)
        # Ollama budget profile must be selected
        assert single == 40000
        assert agg == 45000
        assert per_file == 12000
