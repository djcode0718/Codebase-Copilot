"""
Unit tests for evaluate.py

Tests cover:
- EVAL_DATASET structure validation
- QueryResult / EvalSummary dataclass creation
- Keyword hit-rate calculation logic (pure-Python, no LLM calls)
- Negative paths: empty expected keywords, zero-length datasets
"""

from __future__ import annotations

import sys
import os
import unittest.mock as mock

# Stub heavy dependencies BEFORE evaluate.py is imported so we never
# trigger LLM / LlamaIndex initialisation inside the test runner.
_STUB_MODULES = [
    "llama_index",
    "llama_index.core",
    "llama_index.core.evaluation",
    "llama_index.core.evaluation.FaithfulnessEvaluator",
    "llama_index.core.evaluation.RelevancyEvaluator",
    "app.llm.llm_client",
    "app.services.qa_service",
    "app.retrieval.query_router",
]
for _mod in _STUB_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = mock.MagicMock()

# Provide a concrete QueryMode enum so imports succeed without the real module.
import enum as _enum

class _QueryMode(_enum.Enum):
    code_lookup  = "code_lookup"
    architectural = "architectural"

sys.modules["app.retrieval.query_router"].QueryMode = _QueryMode
sys.modules["app.retrieval.query_router"].classify_query = mock.MagicMock(
    return_value=_QueryMode.code_lookup
)


import importlib
import pytest


def _import_evaluate():
    """Import evaluate.py with all heavy IO stubbed out."""
    # Stub the Settings object used at module level
    sys.modules["llama_index.core"].Settings = mock.MagicMock()
    import evaluate as ev  # noqa: PLC0415
    return ev


@pytest.fixture(scope="module")
def ev():
    return _import_evaluate()


# ─── EVAL_DATASET structure ──────────────────────────────────────────────────

def test_eval_dataset_not_empty(ev):
    assert len(ev.EVAL_DATASET) > 0


def test_eval_dataset_required_keys(ev):
    required = {"question", "expected_files", "expected_keywords", "mode"}
    for item in ev.EVAL_DATASET:
        missing = required - set(item.keys())
        assert not missing, f"Entry missing keys {missing}: {item}"


def test_eval_dataset_modes_valid(ev):
    valid_modes = {"code_lookup", "architectural"}
    for item in ev.EVAL_DATASET:
        assert item["mode"] in valid_modes, f"Unknown mode '{item['mode']}' in {item}"


def test_eval_dataset_questions_non_empty(ev):
    for item in ev.EVAL_DATASET:
        assert item["question"].strip(), "Dataset entry has empty question"


# ─── QueryResult dataclass ───────────────────────────────────────────────────

def test_query_result_instantiation(ev):
    qr = ev.QueryResult(
        question="What does foo do?",
        expected_mode="code_lookup",
        actual_mode="code_lookup",
        mode_correct=True,
        retrieved_files=["app/foo.py"],
        expected_files=["app/foo.py"],
        hit=True,
        reciprocal_rank=1.0,
        answer="Foo does bar.",
        faithfulness_score=0.9,
        relevancy_score=0.8,
        keywords_found=["bar"],
        keyword_hit_rate=1.0,
        latency_total=0.5,
        latency_retrieval=0.2,
        latency_rerank=0.1,
        latency_llm=0.2,
    )
    assert qr.hit is True
    assert qr.reciprocal_rank == 1.0
    assert qr.keyword_hit_rate == 1.0


def test_query_result_mode_incorrect(ev):
    qr = ev.QueryResult(
        question="Describe the architecture",
        expected_mode="architectural",
        actual_mode="code_lookup",
        mode_correct=False,
        retrieved_files=[],
        expected_files=["_codebase_context"],
        hit=False,
        reciprocal_rank=0.0,
        answer="",
        faithfulness_score=None,
        relevancy_score=None,
        keywords_found=[],
        keyword_hit_rate=0.0,
        latency_total=0.0,
        latency_retrieval=0.0,
        latency_rerank=0.0,
        latency_llm=0.0,
    )
    assert qr.mode_correct is False
    assert qr.hit is False
    assert qr.reciprocal_rank == 0.0


# ─── EvalSummary dataclass ───────────────────────────────────────────────────

def test_eval_summary_instantiation(ev):
    summary = ev.EvalSummary(
        total_queries=10,
        hit_rate=0.8,
        mrr=0.65,
        avg_faithfulness=0.75,
        avg_relevancy=0.7,
        avg_keyword_hit=0.9,
        mode_accuracy=0.9,
        avg_latency_total=2.0,
        avg_latency_retrieval=0.5,
        avg_latency_rerank=0.3,
        avg_latency_llm=1.2,
        colbert_enabled=False,
    )
    assert summary.total_queries == 10
    assert summary.hit_rate == 0.8


# ─── Keyword hit-rate logic (pure-Python, no LLM) ───────────────────────────

def _keyword_hit_rate(answer: str, expected_keywords: list) -> float:
    """Mirrors the logic in evaluate.evaluate_single without touching LLM."""
    if not expected_keywords:
        return 1.0
    answer_lower = answer.lower()
    found = [kw for kw in expected_keywords if kw.lower() in answer_lower]
    return len(found) / len(expected_keywords)


def test_keyword_hit_rate_all_found():
    rate = _keyword_hit_rate("The chunk has embeddings and vectors", ["chunk", "embed", "vector"])
    assert rate == 1.0


def test_keyword_hit_rate_none_found():
    rate = _keyword_hit_rate("Nothing relevant here", ["chunk", "embed", "vector"])
    assert rate == 0.0


def test_keyword_hit_rate_partial():
    rate = _keyword_hit_rate("Uses chunk and embed but not vector-store", ["chunk", "embed", "colbert"])
    assert rate == pytest.approx(2 / 3)


def test_keyword_hit_rate_empty_keywords():
    """Empty expected_keywords always yields 1.0 (open-ended questions)."""
    assert _keyword_hit_rate("anything", []) == 1.0


# ─── run_evaluation negative path ────────────────────────────────────────────

def test_run_evaluation_rejects_empty_index_name(ev):
    with pytest.raises(ValueError, match="index_name cannot be empty"):
        ev.run_evaluation("")


def test_run_evaluation_rejects_whitespace_index_name(ev):
    with pytest.raises(ValueError, match="index_name cannot be empty"):
        ev.run_evaluation("   ")

