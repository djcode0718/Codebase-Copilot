# """
# llm_client.py
# ─────────────
# Returns LlamaIndex-compatible LLM and embedding model instances.
# The rest of the pipeline (qa_service, index_builder, query_router, etc.)
# imports from here — so the provider can be swapped via .env without
# touching any other file.

# ── FAST LLM TOGGLE ──────────────────────────────────────────────────────────
# Set USE_FAST_LLM=true in .env to switch the entire project to Groq cloud LLM.

#   USE_FAST_LLM=false (default) → uses LLM_PROVIDER (e.g. local Ollama)
#   USE_FAST_LLM=true            → uses Groq with GROQ_FAST_MODEL

#   GROQ_FAST_MODEL options (set in .env):
#     "llama-3.3-70b-versatile"  → better quality,  ~2-3s latency  (default, good for evals)
#     "llama-3.1-8b-instant"   → faster,          ~0.5-1s latency (good for quick demos)

# Embedding model is ALWAYS local Ollama (nomic-embed-text) — never affected
# by this toggle. Only the generative LLM switches.
# ─────────────────────────────────────────────────────────────────────────────
# """

# import os
# from app.config import (
#     USE_FAST_LLM,
#     GROQ_FAST_MODEL,
#     LLM_PROVIDER,
#     OLLAMA_BASE_URL,
#     OLLAMA_LLM_MODEL,
#     OLLAMA_EMBED_MODEL,
#     GEMINI_API_KEY,
#     GROQ_API_KEY,
#     OPENAI_API_KEY,
# )
# from app.utils.logger import get_logger

# logger = get_logger(__name__)


# def get_llm():
#     """
#     Returns a LlamaIndex LLM instance.

#     Resolution order:
#       1. USE_FAST_LLM=true  → Groq (GROQ_FAST_MODEL), ignores LLM_PROVIDER
#       2. USE_FAST_LLM=false → LLM_PROVIDER (ollama / gemini / groq / openai)

#     This is the single point of control for the generative LLM across the
#     entire project. Every component that needs an LLM calls this function
#     (or picks it up via Settings.llm set in repo_service / main).
#     """

#     # ── FAST LLM ON ───────────────────────────────────────────────────────────
#     # To disable: set USE_FAST_LLM=false in .env
#     if USE_FAST_LLM:
#         logger.info(f"[FAST LLM] Using Groq — model: {GROQ_FAST_MODEL}")
#         from llama_index.llms.groq import Groq
#         return Groq(
#             model=GROQ_FAST_MODEL,
#             api_key=GROQ_API_KEY,
#         )
#     # ── FAST LLM OFF ──────────────────────────────────────────────────────────

#     # Normal provider path — controlled by LLM_PROVIDER in .env
#     logger.info(f"Loading LLM — provider: {LLM_PROVIDER}")

#     if LLM_PROVIDER == "ollama":
#         from llama_index.llms.ollama import Ollama
#         return Ollama(
#             model=OLLAMA_LLM_MODEL,
#             base_url=OLLAMA_BASE_URL,
#             request_timeout=120.0,
#         )

#     elif LLM_PROVIDER == "gemini":
#         from llama_index.llms.gemini import Gemini
#         return Gemini(
#             model="models/gemini-1.5-flash",
#             api_key=GEMINI_API_KEY,
#         )

#     elif LLM_PROVIDER == "groq":
#         from llama_index.llms.groq import Groq
#         return Groq(
#             model="openai/gpt-oss-20b",
#             api_key=GROQ_API_KEY,
#         )

#     elif LLM_PROVIDER == "openai":
#         from llama_index.llms.openai import OpenAI
#         return OpenAI(
#             model="gpt-4o-mini",
#             api_key=OPENAI_API_KEY,
#         )

#     else:
#         raise ValueError(
#             f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. "
#             f"Valid options: ollama, gemini, groq, openai"
#         )


# def get_embed_model():
#     """
#     Returns a LlamaIndex embedding model.

#     Always uses nomic-embed-text via local Ollama — regardless of USE_FAST_LLM
#     or LLM_PROVIDER. Embedding stays local: no API cost, no latency variance,
#     runs fast on M4 unified memory (768-dim dense embeddings).

#     This is intentional: switching the generative LLM should never affect
#     how chunks are embedded or how the index is built.
#     """
#     from llama_index.embeddings.ollama import OllamaEmbedding
#     logger.info(f"Loading embedding model: {OLLAMA_EMBED_MODEL} via Ollama")
#     return OllamaEmbedding(
#         model_name=OLLAMA_EMBED_MODEL,
#         base_url=OLLAMA_BASE_URL,
#     )


# def generate_summary(prompt: str) -> str:
#     """
#     Used by file_map_builder for file-level summarization at index time.
#     Respects USE_FAST_LLM — if the toggle is on, uses Groq for faster
#     indexing too. Falls back gracefully on error.
#     """
#     try:
#         llm = get_llm()
#         response = llm.complete(prompt)
#         return str(response).strip()
#     except Exception as e:
#         logger.error(f"generate_summary failed: {e}")
#         return ""

"""
llm_client.py
─────────────
Returns LlamaIndex-compatible LLM and embedding model instances.

USE_FAST_LLM toggle (set in .env):
  USE_FAST_LLM=true  → Groq (GROQ_FAST_MODEL), ignores LLM_PROVIDER
  USE_FAST_LLM=false → LLM_PROVIDER (ollama / gemini / groq / openai)

Embedding model is ALWAYS local Ollama (nomic-embed-text) — never affected
by this toggle. Only the generative LLM switches.

FIX: LlamaIndex auto-initialises Settings.embed_model to OpenAIEmbedding
at import time when OPENAI_API_KEY is present in the environment.
configure_llamaindex_settings() force-sets both llm and embed_model
unconditionally (no `if None` guard) to override this behaviour.
"""

import os
from app.config import (
    USE_FAST_LLM,
    GROQ_FAST_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    OLLAMA_EMBED_MODEL,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_llm():
    """
    Returns a LlamaIndex LLM instance.

    Resolution order:
      1. USE_FAST_LLM=true  → Groq (GROQ_FAST_MODEL), ignores LLM_PROVIDER
      2. USE_FAST_LLM=false → LLM_PROVIDER (ollama / gemini / groq / openai)
    """
    # ── FAST LLM ON ───────────────────────────────────────────────────────────
    if USE_FAST_LLM:
        logger.info(f"[FAST LLM] Using Groq — model: {GROQ_FAST_MODEL}")
        from llama_index.llms.groq import Groq
        return Groq(
            model=GROQ_FAST_MODEL,
            api_key=GROQ_API_KEY,
        )
    # ── FAST LLM OFF ──────────────────────────────────────────────────────────

    logger.info(f"Loading LLM — provider: {LLM_PROVIDER}")

    if LLM_PROVIDER == "ollama":
        from llama_index.llms.ollama import Ollama
        return Ollama(
            model=OLLAMA_LLM_MODEL,
            base_url=OLLAMA_BASE_URL,
            request_timeout=120.0,
        )

    elif LLM_PROVIDER == "gemini":
        from llama_index.llms.gemini import Gemini
        return Gemini(
            model="models/gemini-1.5-flash",
            api_key=GEMINI_API_KEY,
        )

    elif LLM_PROVIDER == "groq":
        from llama_index.llms.groq import Groq
        # FIX: was "openai/gpt-oss-20b" which is not a valid Groq model name.
        # Using llama-3.3-70b-versatile — Groq's best available model.
        return Groq(
            model="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
        )

    elif LLM_PROVIDER == "openai":
        from llama_index.llms.openai import OpenAI
        return OpenAI(
            model="gpt-4o-mini",
            api_key=OPENAI_API_KEY,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{LLM_PROVIDER}'. "
            f"Valid options: ollama, gemini, groq, openai"
        )


def get_embed_model():
    """
    Returns OllamaEmbedding with nomic-embed-text.

    Always local — never OpenAI, regardless of LLM_PROVIDER or OPENAI_API_KEY.
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

    FIX: LlamaIndex auto-initialises Settings.embed_model = OpenAIEmbedding
    at import time when OPENAI_API_KEY exists in the environment, even before
    any application code runs. The standard `if Settings.llm is None` guard
    therefore never fires for embed_model — it's already set to OpenAI.

    This function sets BOTH values unconditionally, overriding whatever
    LlamaIndex defaulted to. Call this once at startup and once at the
    top of any function that runs in a thread (run_in_executor).
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