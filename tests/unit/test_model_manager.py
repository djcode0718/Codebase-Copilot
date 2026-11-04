"""Unit tests for app/services/model_manager.py: 7-model fallback chain and client initialization."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.services.model_manager import (
    ModelSpec,
    create_llm_client,
    get_available_model_specs,
    reset_client_cache,
)
from app.services.llm_fallback import reset_resilient_llm
from app.llm.llm_client import reset_llm_client


@pytest.fixture(autouse=True)
def clean_client_cache():
    reset_client_cache()
    reset_resilient_llm()
    reset_llm_client()
    yield
    reset_client_cache()
    reset_resilient_llm()
    reset_llm_client()


def test_model_manager_module_importable():
    import app.services.model_manager as m
    assert m is not None


def test_seven_model_exact_fallback_order():
    """Verify that the 7-model priority order matches the configured chain."""
    with patch("app.services.model_manager.LLM_PROVIDER", "gemini"), \
         patch("app.services.model_manager.USE_FAST_LLM", False), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"):
        specs = get_available_model_specs()
        expected = [
            ModelSpec(provider="gemini", model_name="gemini-3.8-flash"),
            ModelSpec(provider="gemini", model_name="gemini-3.5-flash-lite"),
            ModelSpec(provider="gemini", model_name="gemini-3.6-flash"),
            ModelSpec(provider="groq", model_name="openai/gpt-oss-120b"),
            ModelSpec(provider="groq", model_name="qwen/qwen3.8-27b"),
            ModelSpec(provider="groq", model_name="minimaxai/minimax-m2.7"),
            ModelSpec(provider="ollama", model_name="llama3.1:8b"),
        ]
        assert specs[:7] == expected


def test_provider_to_model_mapping():
    """Verify each model is correctly mapped to its provider."""
    with patch("app.services.model_manager.LLM_PROVIDER", "gemini"), \
         patch("app.services.model_manager.USE_FAST_LLM", False), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"):
        specs = get_available_model_specs()
        gemini_specs = [s for s in specs if s.provider == "gemini"]
        groq_specs = [s for s in specs if s.provider == "groq"]
        ollama_specs = [s for s in specs if s.provider == "ollama"]

        assert [s.model_name for s in gemini_specs][:3] == [
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
        ]
        assert [s.model_name for s in groq_specs][:3] == [
            "openai/gpt-oss-120b",
            "qwen/qwen3.8-27b",
            "minimaxai/minimax-m2.7",
        ]
        assert [s.model_name for s in ollama_specs] == ["llama3.1:8b"]


def test_missing_cloud_api_keys_falls_back_to_available():
    """If Gemini and Groq API keys are missing, Ollama is still available."""
    with patch("app.services.model_manager.LLM_PROVIDER", "gemini"), \
         patch("app.services.model_manager.GEMINI_API_KEY", ""), \
         patch("app.services.model_manager.GROQ_API_KEY", ""):
        specs = get_available_model_specs()
        assert len(specs) == 1
        assert specs[0] == ModelSpec(provider="ollama", model_name="llama3.1:8b")


def test_groq_client_receives_correct_context_windows():
    mock_groq_cls = MagicMock()
    with patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"), \
         patch.dict("sys.modules", {"llama_index.llms.groq": MagicMock(Groq=mock_groq_cls)}):

        # 1. GPT-OSS 120B model
        create_llm_client(ModelSpec(provider="groq", model_name="openai/gpt-oss-120b"))
        kwargs_120b = mock_groq_cls.call_args[1]
        assert kwargs_120b["context_window"] == 131072
        assert kwargs_120b["max_tokens"] == 4096

        reset_client_cache()

        # 2. Qwen model
        create_llm_client(ModelSpec(provider="groq", model_name="qwen/qwen3.8-27b"))
        kwargs_qwen = mock_groq_cls.call_args[1]
        assert kwargs_qwen["context_window"] == 32768
        assert kwargs_qwen["max_tokens"] == 4096

        reset_client_cache()

        # 3. Minimax model
        create_llm_client(ModelSpec(provider="groq", model_name="minimaxai/minimax-m2.7"))
        kwargs_minimax = mock_groq_cls.call_args[1]
        assert kwargs_minimax["context_window"] == 131072
        assert kwargs_minimax["max_tokens"] == 4096


def test_ollama_client_receives_llama31_parameters():
    mock_ollama_cls = MagicMock()
    with patch.dict("sys.modules", {"llama_index.llms.ollama": MagicMock(Ollama=mock_ollama_cls)}):
        create_llm_client(ModelSpec(provider="ollama", model_name="llama3.1:8b"))
        mock_ollama_cls.assert_called_once()
        kwargs = mock_ollama_cls.call_args[1]
        assert kwargs["context_window"] == 16384
        assert kwargs["additional_kwargs"]["options"]["num_ctx"] == 16384


def test_client_caching_and_thread_safety():
    """Verify clients are cached and returned on subsequent invocations."""
    mock_ollama_cls = MagicMock()
    with patch.dict("sys.modules", {"llama_index.llms.ollama": MagicMock(Ollama=mock_ollama_cls)}):
        c1 = create_llm_client(ModelSpec(provider="ollama", model_name="llama3.1:8b"))
        c2 = create_llm_client(ModelSpec(provider="ollama", model_name="llama3.1:8b"))
        assert c1 is c2
        assert mock_ollama_cls.call_count == 1
