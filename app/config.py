import os
from dotenv import load_dotenv

load_dotenv()

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