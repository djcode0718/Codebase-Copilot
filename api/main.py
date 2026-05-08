"""
api/main.py
───────────
FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000

Make sure you're running from the project root (codebase-copilot/):
    cd /path/to/codebase-copilot
    uvicorn api.main:app --reload --port 8000
"""

import sys
import os

# Ensure project root is on the path so 'app' module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import repo, chat, eval, suggestions

# ── Boot LlamaIndex settings once at startup ──────────────────────────────────
# This prevents the first request from being slow due to model loading.
from llama_index.core import Settings
from app.llm.llm_client import get_llm, get_embed_model

def _init_llamaindex():
    if Settings.llm is None:
        Settings.llm = get_llm()
    if Settings.embed_model is None:
        Settings.embed_model = get_embed_model()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Codebase Copilot API",
    description="AI-powered codebase intelligence — hybrid retrieval, reranking, dual-mode routing.",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allows the Next.js dev server (localhost:3000) and production domain.
# Tighten allow_origins in production to your actual domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(repo.router,        prefix="/api/repo",        tags=["Repository"])
app.include_router(chat.router,        prefix="/api/chat",        tags=["Chat"])
app.include_router(eval.router,        prefix="/api/eval",        tags=["Evaluation"])
app.include_router(suggestions.router, prefix="/api/repo",        tags=["Suggestions"])


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Pre-load LlamaIndex LLM + embedding model so first request is fast."""
    try:
        _init_llamaindex()
    except Exception as e:
        # Don't crash startup — just log. Models might not be available yet.
        print(f"[startup] LlamaIndex init warning: {e}")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    from app.config import LLM_PROVIDER, USE_COLBERT, USE_FAST_LLM
    return {
        "status": "ok",
        "llm_provider": LLM_PROVIDER,
        "use_fast_llm": USE_FAST_LLM,
        "colbert_enabled": USE_COLBERT,
    }
