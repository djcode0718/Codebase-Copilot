import pytest
from unittest.mock import patch, MagicMock

from app.retrieval.query_router import (
    detect_excluded_folder,
    detect_aggregation,
    has_superlative,
    match_adjective_action,
    check_superlative_intent,
    LOW_CONFIDENCE_SIMILARITY_THRESHOLD
)


def test_detect_excluded_folder():
    # 1. Matching case
    assert detect_excluded_folder("what is inside node_modules/lodash?") == "node_modules"
    assert detect_excluded_folder("check venv files") == "venv"
    assert detect_excluded_folder("build/output.js path") == "build"
    
    # 2. Non-matching case
    assert detect_excluded_folder("how many files in src/api?") is None
    assert detect_excluded_folder("what is the main entry point") is None


def test_detect_aggregation():
    # 1. Matching cases
    assert detect_aggregation("how many tests do we have") is True
    assert detect_aggregation("total number of files") is True
    assert detect_aggregation("give me count of controllers") is True
    assert detect_aggregation("list all endpoints in router") is True
    
    # 2. Non-matching cases
    assert detect_aggregation("what does this function do") is False
    assert detect_aggregation("explain main.py architecture") is False


def test_has_superlative():
    # 1. Matching cases
    assert has_superlative("who is the most active user") is True
    assert has_superlative("least tested file") is True
    assert has_superlative("find the best approach") is True
    assert has_superlative("what is the messiest function") is True
    assert has_superlative("riskiest code blocks") is True
    
    # 2. Non-matching cases
    assert has_superlative("average complexity of code") is False
    assert has_superlative("how to clean up tech debt") is False


def test_match_adjective_action():
    # Adjective mapping matches
    assert match_adjective_action("most vulnerable component") == "security_review"
    assert match_adjective_action("riskiest tech debt") == "tech_debt_scan"
    assert match_adjective_action("least tested route") == "test_intelligence"
    assert match_adjective_action("highly coupled files") == "dependency_graph"
    
    # No match
    assert match_adjective_action("most complex logic") == "tech_debt_scan"  # matches "complex" -> tech_debt_scan
    assert match_adjective_action("cleanest code") is None


def test_check_superlative_intent_adjective_path():
    # Deterministic mapping paths (should not trigger LLM call)
    with patch("app.retrieval.query_router.classify_superlative_with_llm") as mock_llm:
        res = check_superlative_intent("tell me the most vulnerable file")
        assert res is not None
        assert res["suggested_action"] == "security_review"
        assert "Security Review" in res["message"]
        mock_llm.assert_not_called()


def test_check_superlative_intent_llm_fallback_path():
    # Fallback path (should trigger LLM call when has_superlative is True but adjective map fails)
    with patch("app.retrieval.query_router.classify_superlative_with_llm", return_value="security_review") as mock_llm:
        res = check_superlative_intent("who is the best coder here")
        assert res is not None
        assert res["suggested_action"] == "security_review"
        mock_llm.assert_called_once_with("who is the best coder here")

    # LLM fallback fails or returns None -> check_superlative_intent should return None
    with patch("app.retrieval.query_router.classify_superlative_with_llm", return_value=None) as mock_llm:
        res = check_superlative_intent("who is the best coder here")
        assert res is None


def test_threshold_value():
    assert LOW_CONFIDENCE_SIMILARITY_THRESHOLD == 0.40
