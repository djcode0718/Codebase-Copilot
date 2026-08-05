import os
from dotenv import load_dotenv

import sys
load_dotenv(override="pytest" not in sys.modules)

# ─── LLM Provider ────────────────────────────────────────────────────────────
# Options: "ollama" | "gemini" | "groq" | "openai"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# ─── Fast LLM Toggle ─────────────────────────────────────────────────────────
# Set USE_FAST_LLM=true in .env to switch the entire project to Groq cloud LLM.
# Useful for: evaluation runs, demos, faster iteration.
#
# When True  → get_llm() returns Groq (GROQ_FAST_MODEL), ~2-3s per query
# When False → get_llm() returns whatever LLM_PROVIDER is set to, e.g. Ollama
#
# Embedding model is ALWAYS local Ollama (nomic-embed-text) regardless of this toggle.
# Only the generative LLM switches.
#
# TO ENABLE  → set USE_FAST_LLM=true  in .env  (or flip the default below)
# TO DISABLE → set USE_FAST_LLM=false in .env
USE_FAST_LLM = os.getenv("USE_FAST_LLM", "false").lower() == "true"

# ─── Groq Fast Model ─────────────────────────────────────────────────────────
# Used only when USE_FAST_LLM=true.
# Swap between these two in .env to compare speed vs quality:
#   "llama-3.3-70b-versatile"  → better quality,  ~2-3s latency  (recommended for evals)
#   "llama-3.1-8b-instant"   → faster,          ~0.5-1s latency (good for quick demos)
GROQ_FAST_MODEL = os.getenv("GROQ_FAST_MODEL", "llama-3.3-70b-versatile")

# ─── API Keys ────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")

# ─── Ollama ───────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL   = os.getenv("OLLAMA_LLM_MODEL", "llama3.2:3b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# ─── Directories ─────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR  = os.path.join(BASE_DIR, "data")
REPOS_DIR = os.path.join(DATA_DIR, "repos")
INDEX_DIR = os.path.join(DATA_DIR, "index")

os.makedirs(REPOS_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)


def get_repos_dir() -> str:
    """Return repositories directory path for lazy consumers."""
    return REPOS_DIR


def get_index_dir() -> str:
    """Return index directory path for lazy consumers."""
    return INDEX_DIR

# ─── Retrieval ────────────────────────────────────────────────────────────────
TOP_K_FILES   = 3    # files returned by DocumentSummaryIndex coarse pass
TOP_K_CHUNKS  = 10   # chunks returned by hybrid retriever before rerank
TOP_K_RERANK  = 5    # final chunks passed to LLM prompt

# ─── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_LINES        = 50    # lines per chunk for CodeSplitter
CHUNK_MAX_CHARS    = 1500  # hard char cap per chunk

# ─── ColBERT ──────────────────────────────────────────────────────────────────
# Set to False to disable ColBERT reranking entirely.
# When False: pipeline uses RRF fusion scores from QueryFusionRetriever.
# When True:  ColBERT reranks the top TOP_K_CHUNKS results (~2-3s extra/query).
#
# TO DISABLE COLBERT: set USE_COLBERT=false in .env
USE_COLBERT = os.getenv("USE_COLBERT", "true").lower() == "true"

# ─── LLM Fallback Configuration ──────────────────────────────────────────────
# Maximum retry-after delay (in seconds) that we will wait for before falling back to the next model.
LLM_FALLBACK_RETRY_THRESHOLD = int(os.getenv("LLM_FALLBACK_RETRY_THRESHOLD", "10"))

# Configured fallback chain of model definitions (comma-separated "provider:model_name").
LLM_FALLBACK_CHAIN_STR = os.getenv(
    "LLM_FALLBACK_CHAIN",
    "gemini:models/gemini-3.6-flash,"
    "gemini:models/gemini-3.1-flash-lite,"
    "gemini:models/gemini-2.0-flash,"
    "gemini:models/gemini-2.0-flash-lite,"
    "gemini:models/gemini-flash-latest,"
    "groq:llama-3.3-70b-versatile"
)

# ─── Streaming Guard Configuration ───────────────────────────────────────────
# Maximum time to wait for the first streamed token before returning a
# guaranteed fallback response so the UI does not stay pending.
STREAM_FIRST_TOKEN_TIMEOUT_SECONDS = float(os.getenv("STREAM_FIRST_TOKEN_TIMEOUT_SECONDS", "8"))
# Optional override for the startup-time fallback text.
STREAM_FIRST_TOKEN_FALLBACK_TEXT = os.getenv("STREAM_FIRST_TOKEN_FALLBACK_TEXT", "").strip()

# -- Startup prewarm controls -------------------------------------------------
# Disable by default to keep API startup fast in local dev.
LLAMAINDEX_PREWARM_ON_STARTUP = os.getenv("LLAMAINDEX_PREWARM_ON_STARTUP", "false").lower() == "true"
# Optional delay before background prewarm task starts.
LLAMAINDEX_PREWARM_DELAY_SECONDS = float(os.getenv("LLAMAINDEX_PREWARM_DELAY_SECONDS", "0"))
