"""
llm_client.py
─────────────
Returns LlamaIndex-compatible LLM and embedding model instances.

USE_FAST_LLM toggle (set in .env):
  USE_FAST_LLM=true  → Groq (GROQ_FAST_MODEL), ignores LLM_PROVIDER
  USE_FAST_LLM=false → LLM_PROVIDER (ollama / gemini / groq)

Embedding model is ALWAYS local Ollama (nomic-embed-text) — never affected
by this toggle. Only the generative LLM switches.

configure_llamaindex_settings() force-sets both llm and embed_model
unconditionally (no `if None` guard) to avoid accidental default provider drift.
"""

from app.config import (
    USE_FAST_LLM,
    GROQ_FAST_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_llm():
    """
    Returns a resilient LLM that automatically falls back across all
    available configured providers/models.
    """
    from app.services.llm_fallback import get_resilient_llm

    logger.info(
        "Loading resilient LLM manager (provider=%s, fast_mode=%s, fast_model=%s)",
        LLM_PROVIDER,
        USE_FAST_LLM,
        GROQ_FAST_MODEL,
    )
    return get_resilient_llm()


def get_embed_model():
    """
    Returns OllamaEmbedding with nomic-embed-text.

    Always local, regardless of configured generative provider.
    """
    from llama_index.embeddings.ollama import OllamaEmbedding
    logger.info(f"Loading embedding model: {OLLAMA_EMBED_MODEL} via Ollama")
    return OllamaEmbedding(
        model_name=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )


def configure_llamaindex_settings():
    """
    Force-set LlamaIndex global Settings to use our LLM and embed model.

    This function sets BOTH values unconditionally so app configuration always
    wins over library defaults.
    """
    from llama_index.core import Settings

    # Always override — do NOT use `if None` guards here
    Settings.llm = get_llm()
    Settings.embed_model = get_embed_model()

    logger.info(
        f"LlamaIndex configured — LLM: {LLM_PROVIDER}, "
        f"embed: {OLLAMA_EMBED_MODEL} (Ollama)"
    )


def generate_summary(prompt: str) -> str:
    """
    Used by context_builder for file-level summarization at index time.
    """
    try:
        llm = get_llm()
        response = llm.complete(prompt)
        return str(response).strip()
    except Exception as e:
        logger.error(f"generate_summary failed: {e}")
        return ""