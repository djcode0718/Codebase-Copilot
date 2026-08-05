# """
# api/main.py
# ───────────
# FastAPI application entry point.

# Run with:
#     uvicorn api.main:app --reload --port 8000

# Make sure you're running from the project root (codebase-copilot/):
#     cd /path/to/codebase-copilot
#     uvicorn api.main:app --reload --port 8000
# """

# import sys
# import os

# # Ensure project root is on the path so 'app' module is importable
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from api.routers import repo, chat, eval, suggestions

# # ── Boot LlamaIndex settings once at startup ──────────────────────────────────
# # This prevents the first request from being slow due to model loading.
# from llama_index.core import Settings
# from app.llm.llm_client import get_llm, get_embed_model

# def _init_llamaindex():
#     if Settings.llm is None:
#         Settings.llm = get_llm()
#     if Settings.embed_model is None:
#         Settings.embed_model = get_embed_model()


# print("OLLAMA EMBED:", os.getenv("OLLAMA_EMBED_MODEL"))
# print("LLM PROVIDER:", os.getenv("LLM_PROVIDER"))

# # ── App ───────────────────────────────────────────────────────────────────────
# app = FastAPI(
#     title="Codebase Copilot API",
#     description="AI-powered codebase intelligence — hybrid retrieval, reranking, dual-mode routing.",
#     version="1.0.0",
# )

# # ── CORS ──────────────────────────────────────────────────────────────────────
# # Allows the Next.js dev server (localhost:3000) and production domain.
# # Tighten allow_origins in production to your actual domain.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:3000",
#         "http://localhost:3001",
#         os.getenv("FRONTEND_URL", "http://localhost:3000"),
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ── Routers ───────────────────────────────────────────────────────────────────
# app.include_router(repo.router,        prefix="/api/repo",        tags=["Repository"])
# app.include_router(chat.router,        prefix="/api/chat",        tags=["Chat"])
# app.include_router(eval.router,        prefix="/api/eval",        tags=["Evaluation"])
# app.include_router(suggestions.router, prefix="/api/repo",        tags=["Suggestions"])


# # ── Startup ───────────────────────────────────────────────────────────────────
# @app.on_event("startup")
# async def startup_event():
#     """Pre-load LlamaIndex LLM + embedding model so first request is fast."""
#     try:
#         _init_llamaindex()
#     except Exception as e:
#         # Don't crash startup — just log. Models might not be available yet.
#         print(f"[startup] LlamaIndex init warning: {e}")


# # ── Health check ──────────────────────────────────────────────────────────────
# @app.get("/api/health")
# async def health():
#     from app.config import LLM_PROVIDER, USE_COLBERT, USE_FAST_LLM
#     return {
#         "status": "ok",
#         "llm_provider": LLM_PROVIDER,
#         "use_fast_llm": USE_FAST_LLM,
#         "colbert_enabled": USE_COLBERT,
#     }


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
import asyncio

# Ensure project root is on the path so 'app' module is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import repo, chat, eval, suggestions, health, reviews

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Codebase Copilot API",
    description="AI-powered codebase intelligence — hybrid retrieval, reranking, dual-mode routing.",
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
frontend_url = os.getenv("FRONTEND_URL")
dev_allowed_origins = os.getenv("DEV_ALLOWED_ORIGINS", "")
allow_origins = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://[::1]:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://[::1]:3001",
}
if frontend_url and frontend_url.strip():
    allow_origins.add(frontend_url.strip())
for origin in dev_allowed_origins.split(","):
    origin = origin.strip()
    if not origin:
        continue
    if origin.startswith("http://") or origin.startswith("https://"):
        allow_origins.add(origin)
    else:
        allow_origins.add(f"http://{origin}:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allow_origins),
    # Accept localhost and RFC1918 hosts for local/mobile dev frontends.
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\]|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(repo.router,        prefix="/api/repo",  tags=["Repository"])
app.include_router(chat.router,        prefix="/api/chat",  tags=["Chat"])
app.include_router(eval.router,        prefix="/api/eval",  tags=["Evaluation"])
app.include_router(suggestions.router, prefix="/api/repo",  tags=["Suggestions"])
app.include_router(health.router,      prefix="/api/repo",  tags=["Repository Health"])
app.include_router(reviews.router,     prefix="/api/reviews", tags=["Engineering Review"])


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """
    Force-configure LlamaIndex to use Groq + Ollama embeddings when available.

    ROOT-CAUSE FIX (startup failure):
    configure_llamaindex_settings() makes synchronous HTTP calls to initialise
    LLM provider clients (e.g. Gemini API validation).  Running this directly
    in the async task without an executor blocks the entire asyncio event loop,
    which prevents uvicorn from printing "Application startup complete" and from
    responding to health-check probes.  The fix is two-fold:

    1. A minimum 5-second delay ensures the server is fully bound and serving
       before the prewarm task wakes up, so Wait-ForPortsReady in start.ps1
       can confirm readiness immediately.
    2. configure_llamaindex_settings() is offloaded to a thread-pool executor
       via loop.run_in_executor() so it never blocks the event loop.
    """
    try:
        from app.config import LLAMAINDEX_PREWARM_ON_STARTUP, LLAMAINDEX_PREWARM_DELAY_SECONDS
        if not LLAMAINDEX_PREWARM_ON_STARTUP:
            return

        async def _prewarm_llamaindex() -> None:
            # Guarantee a minimum 5-second head-start so the server is already
            # accepting connections before any blocking LLM init begins.
            delay = max(float(LLAMAINDEX_PREWARM_DELAY_SECONDS), 5.0)
            await asyncio.sleep(delay)
            try:
                from app.llm.llm_client import configure_llamaindex_settings
                loop = asyncio.get_running_loop()
                # Run synchronous (possibly network-bound) LLM init in a
                # thread-pool executor so it never stalls the event loop.
                await loop.run_in_executor(None, configure_llamaindex_settings)
            except ModuleNotFoundError:
                pass
            except Exception as prewarm_err:
                print(f"[startup] LlamaIndex prewarm warning: {prewarm_err}")

        # Non-blocking prewarm keeps API startup quick while still allowing optional warmup.
        asyncio.create_task(_prewarm_llamaindex())
    except ModuleNotFoundError:
        # Optional dependency is not installed in minimal backend setups.
        # Startup should stay clean and allow non-AI endpoints to run.
        pass
    except Exception as e:
        # Don't crash startup — Ollama or provider credentials may be unavailable.
        print(f"[startup] LlamaIndex config warning: {e}")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    from app.config import LLM_PROVIDER, USE_COLBERT, USE_FAST_LLM, OLLAMA_EMBED_MODEL

    return {
        "status": "ok",
        "llm_provider": LLM_PROVIDER,
        "use_fast_llm": USE_FAST_LLM,
        "colbert_enabled": USE_COLBERT,
        # Keep health checks fast and deterministic (no heavy optional imports).
        "embed_model": OLLAMA_EMBED_MODEL,
    }

