"""
tests/test_app_config.py
Unit tests for app/config.py â€” env var loading, defaults, directory creation.
Pure Python, no external services needed.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
import importlib
from unittest.mock import patch


def reload_config(env_overrides: dict):
    """Re-import config with patched env vars and return the fresh module."""
    with patch.dict(os.environ, env_overrides, clear=False):
        import app.config as cfg
        importlib.reload(cfg)
        return cfg


class TestLLMProviderConfig:
    def test_default_llm_provider_is_ollama(self):
        cfg = reload_config({"LLM_PROVIDER": "ollama"})
        assert cfg.LLM_PROVIDER == "ollama"

    def test_llm_provider_groq(self):
        cfg = reload_config({"LLM_PROVIDER": "GROQ"})
        assert cfg.LLM_PROVIDER == "groq"  # lowercased

    def test_llm_provider_gemini(self):
        cfg = reload_config({"LLM_PROVIDER": "Gemini"})
        assert cfg.LLM_PROVIDER == "gemini"

class TestFastLLMToggle:
    def test_use_fast_llm_false_by_default(self):
        cfg = reload_config({"USE_FAST_LLM": "false"})
        assert cfg.USE_FAST_LLM is False

    def test_use_fast_llm_true(self):
        cfg = reload_config({"USE_FAST_LLM": "true"})
        assert cfg.USE_FAST_LLM is True

    def test_use_fast_llm_case_insensitive(self):
        cfg = reload_config({"USE_FAST_LLM": "TRUE"})
        assert cfg.USE_FAST_LLM is True

    def test_use_fast_llm_invalid_defaults_false(self):
        cfg = reload_config({"USE_FAST_LLM": "yes"})
        assert cfg.USE_FAST_LLM is False

    def test_groq_fast_model_is_a_non_empty_string(self):
        """GROQ_FAST_MODEL must be set to a non-empty model name (may come from .env)."""
        cfg = reload_config({})
        assert isinstance(cfg.GROQ_FAST_MODEL, str)
        assert len(cfg.GROQ_FAST_MODEL) > 0

    def test_groq_fast_model_can_be_70b(self):
        cfg = reload_config({"GROQ_FAST_MODEL": "llama-3.3-70b-versatile"})
        assert cfg.GROQ_FAST_MODEL == "llama-3.3-70b-versatile"

    def test_groq_fast_model_custom(self):
        cfg = reload_config({"GROQ_FAST_MODEL": "llama-3.1-8b-instant"})
        assert cfg.GROQ_FAST_MODEL == "llama-3.1-8b-instant"


class TestAPIKeys:
    def test_api_keys_are_strings(self):
        import app.config as cfg
        assert isinstance(cfg.GEMINI_API_KEY, str)
        assert isinstance(cfg.GROQ_API_KEY, str)

    def test_missing_key_defaults_to_empty_string(self):
        cfg = reload_config({"GEMINI_API_KEY": "", "GROQ_API_KEY": ""})
        assert cfg.GEMINI_API_KEY == ""
        assert cfg.GROQ_API_KEY == ""

    def test_custom_api_key(self):
        cfg = reload_config({"GROQ_API_KEY": "test-groq-key-123"})
        assert cfg.GROQ_API_KEY == "test-groq-key-123"


class TestOllamaConfig:
    def test_default_base_url(self):
        cfg = reload_config({"OLLAMA_BASE_URL": "http://localhost:11434"})
        assert cfg.OLLAMA_BASE_URL == "http://localhost:11434"

    def test_custom_base_url(self):
        cfg = reload_config({"OLLAMA_BASE_URL": "http://192.168.1.10:11434"})
        assert cfg.OLLAMA_BASE_URL == "http://192.168.1.10:11434"

    def test_default_embed_model(self):
        cfg = reload_config({"OLLAMA_EMBED_MODEL": "nomic-embed-text"})
        assert cfg.OLLAMA_EMBED_MODEL == "nomic-embed-text"

    def test_custom_llm_model(self):
        cfg = reload_config({"OLLAMA_LLM_MODEL": "mistral"})
        assert cfg.OLLAMA_LLM_MODEL == "mistral"

    def test_ollama_model_alias(self):
        cfg = reload_config({"OLLAMA_MODEL": "llama3:8b", "OLLAMA_LLM_MODEL": ""})
        assert cfg.OLLAMA_LLM_MODEL == "llama3:8b"


class TestProviderModelConfig:
    def test_default_provider_models_are_non_empty(self):
        import app.config as cfg
        assert isinstance(cfg.GEMINI_LLM_MODEL, str) and cfg.GEMINI_LLM_MODEL
        assert isinstance(cfg.GROQ_LLM_MODEL, str) and cfg.GROQ_LLM_MODEL

    def test_custom_provider_models(self):
        cfg = reload_config({
            "GEMINI_LLM_MODEL": "models/gemini-2.0-flash",
            "GROQ_LLM_MODEL": "llama-3.1-8b-instant",
        })
        assert cfg.GEMINI_LLM_MODEL == "models/gemini-2.0-flash"
        assert cfg.GROQ_LLM_MODEL == "llama-3.1-8b-instant"


class TestDirectories:
    def test_dirs_are_strings(self):
        import app.config as cfg
        assert isinstance(cfg.BASE_DIR, str)
        assert isinstance(cfg.DATA_DIR, str)
        assert isinstance(cfg.REPOS_DIR, str)
        assert isinstance(cfg.INDEX_DIR, str)

    def test_repos_dir_under_data(self):
        old_repos = os.environ.pop("REPOS_DIR", None)
        try:
            cfg = reload_config({})
            assert cfg.REPOS_DIR.startswith(cfg.DATA_DIR)
        finally:
            if old_repos is not None:
                os.environ["REPOS_DIR"] = old_repos

    def test_index_dir_under_data(self):
        old_index = os.environ.pop("INDEX_DIR", None)
        try:
            cfg = reload_config({})
            assert cfg.INDEX_DIR.startswith(cfg.DATA_DIR)
        finally:
            if old_index is not None:
                os.environ["INDEX_DIR"] = old_index

    def test_dirs_are_created(self):
        import app.config as cfg
        assert os.path.isdir(cfg.REPOS_DIR)
        assert os.path.isdir(cfg.INDEX_DIR)


class TestRetrievalConfig:
    def test_top_k_values_are_positive_integers(self):
        import app.config as cfg
        assert isinstance(cfg.TOP_K_FILES, int) and cfg.TOP_K_FILES > 0
        assert isinstance(cfg.TOP_K_CHUNKS, int) and cfg.TOP_K_CHUNKS > 0
        assert isinstance(cfg.TOP_K_RERANK, int) and cfg.TOP_K_RERANK > 0

    def test_rerank_less_than_or_equal_to_chunks(self):
        import app.config as cfg
        assert cfg.TOP_K_RERANK <= cfg.TOP_K_CHUNKS

    def test_chunk_lines_positive(self):
        import app.config as cfg
        assert cfg.CHUNK_LINES > 0

    def test_chunk_max_chars_positive(self):
        import app.config as cfg
        assert cfg.CHUNK_MAX_CHARS > 0


class TestRerankerConfig:
    def test_use_reranker_is_bool(self):
        import app.config as cfg
        assert isinstance(cfg.USE_RERANKER, bool)

    def test_use_reranker_false(self):
        cfg = reload_config({"USE_RERANKER": "false"})
        assert cfg.USE_RERANKER is False

    def test_use_reranker_true(self):
        cfg = reload_config({"USE_RERANKER": "true"})
        assert cfg.USE_RERANKER is True

    def test_use_reranker_case_insensitive(self):
        cfg = reload_config({"USE_RERANKER": "TRUE"})
        assert cfg.USE_RERANKER is True

    def test_use_reranker_fallback_to_cross_encoder_and_colbert(self):
        old_val = os.environ.pop("USE_RERANKER", None)
        old_cross = os.environ.pop("USE_CROSS_ENCODER", None)
        old_colbert = os.environ.pop("USE_COLBERT", None)
        try:
            cfg = reload_config({"USE_CROSS_ENCODER": "false"})
            assert cfg.USE_RERANKER is False
            cfg = reload_config({"USE_CROSS_ENCODER": "true"})
            assert cfg.USE_RERANKER is True

            cfg = reload_config({"USE_COLBERT": "false"})
            assert cfg.USE_RERANKER is False
            cfg = reload_config({"USE_COLBERT": "true"})
            assert cfg.USE_RERANKER is True
        finally:
            if old_val is not None:
                os.environ["USE_RERANKER"] = old_val
            if old_cross is not None:
                os.environ["USE_CROSS_ENCODER"] = old_cross
            if old_colbert is not None:
                os.environ["USE_COLBERT"] = old_colbert


