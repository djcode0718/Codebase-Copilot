"""Unit tests for app/services/model_manager.py: provider isolation and client initialization."""
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


def test_cloud_gemini_mode_excludes_ollama():
    with patch("app.services.model_manager.LLM_PROVIDER", "gemini"), \
         patch("app.services.model_manager.USE_FAST_LLM", False), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"):
        specs = get_available_model_specs()
        assert len(specs) > 0
        assert specs[0].provider == "gemini"
        assert all(s.provider in ("gemini", "groq") for s in specs)
        assert not any(s.provider == "ollama" for s in specs)


def test_cloud_groq_mode_excludes_ollama():
    with patch("app.services.model_manager.LLM_PROVIDER", "groq"), \
         patch("app.services.model_manager.USE_FAST_LLM", False), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"):
        specs = get_available_model_specs()
        assert len(specs) > 0
        assert specs[0].provider == "groq"
        assert all(s.provider in ("gemini", "groq") for s in specs)
        assert not any(s.provider == "ollama" for s in specs)


def test_offline_mode_selects_strictly_llama31_8b():
    with patch("app.services.model_manager.LLM_PROVIDER", "ollama"), \
         patch("app.services.model_manager.USE_FAST_LLM", False), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"):
        specs = get_available_model_specs()
        assert specs == [ModelSpec(provider="ollama", model_name="llama3.1:8b")]
        assert not any(s.provider in ("gemini", "groq") for s in specs)


def test_offline_mode_ignores_use_fast_llm_true():
    with patch("app.services.model_manager.LLM_PROVIDER", "ollama"), \
         patch("app.services.model_manager.USE_FAST_LLM", True), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"):
        specs = get_available_model_specs()
        assert specs == [ModelSpec(provider="ollama", model_name="llama3.1:8b")]
        assert specs[0].provider == "ollama"
        assert specs[0].model_name == "llama3.1:8b"


def test_offline_mode_never_falls_back_to_cloud_on_failure():
    from app.services.llm_fallback import ResilientFallbackLLM, AllModelsExhaustedError

    mock_ollama_client = MagicMock()
    mock_ollama_client._cb_provider = "ollama"
    mock_ollama_client._cb_model_name = "llama3.1:8b"
    mock_ollama_client.complete.side_effect = ConnectionError("Ollama daemon unreachable")

    with patch("app.services.model_manager.LLM_PROVIDER", "ollama"), \
         patch("app.services.model_manager.USE_FAST_LLM", False), \
         patch("app.services.model_manager.GEMINI_API_KEY", "mock-gemini-key"), \
         patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"), \
         patch("app.services.model_manager.create_llm_client", return_value=mock_ollama_client):
        specs = get_available_model_specs()
        assert len(specs) == 1
        assert specs[0].provider == "ollama"

        llm = ResilientFallbackLLM(fallback_chain=[mock_ollama_client])
        with pytest.raises(AllModelsExhaustedError) as exc_info:
            llm.complete("test prompt")
        assert "ollama/llama3.1:8b" in exc_info.value.errors
        assert "gemini" not in exc_info.value.errors
        assert "groq" not in exc_info.value.errors


def test_invalid_llm_provider_raises_value_error():
    with patch("app.services.model_manager.LLM_PROVIDER", "unsupported_provider"):
        with pytest.raises(ValueError) as exc_info:
            get_available_model_specs()
        assert "Invalid LLM_PROVIDER" in str(exc_info.value)


def test_ollama_client_receives_runtime_num_ctx():
    mock_ollama_cls = MagicMock()
    with patch.dict("sys.modules", {"llama_index.llms.ollama": MagicMock(Ollama=mock_ollama_cls)}):
        create_llm_client(ModelSpec(provider="ollama", model_name="llama3.1:8b"))
        mock_ollama_cls.assert_called_once()
        kwargs = mock_ollama_cls.call_args[1]
        assert kwargs["context_window"] == 16384
        assert kwargs["additional_kwargs"]["options"]["num_ctx"] == 16384


def test_groq_client_receives_corrected_context_and_bounded_output():
    mock_groq_cls = MagicMock()
    with patch("app.services.model_manager.GROQ_API_KEY", "mock-groq-key"), \
         patch.dict("sys.modules", {"llama_index.llms.groq": MagicMock(Groq=mock_groq_cls)}):
        # Test 1: Qwen model gets 32,768 context and 4,096 max_tokens
        create_llm_client(ModelSpec(provider="groq", model_name="qwen/qwen3.8-27b"))
        kwargs_qwen = mock_groq_cls.call_args_list[0][1]
        assert kwargs_qwen["context_window"] == 32768
        assert kwargs_qwen["max_tokens"] == 4096

        reset_client_cache()

        # Test 2: 70b model gets 131,072 context and 4,096 max_tokens
        create_llm_client(ModelSpec(provider="groq", model_name="llama-3.3-70b-versatile"))
        kwargs_70b = mock_groq_cls.call_args_list[1][1]
        assert kwargs_70b["context_window"] == 131072
        assert kwargs_70b["max_tokens"] == 4096
