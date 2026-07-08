"""
api/services/chat_service.py
─────────────────────────────
Wraps app/services/qa_service.handle_user_query() and streams the response
as Server-Sent Events.

Session state (chat_engine + memory) is cached in-process per (repo_id, chat_id)
so multi-turn conversation works correctly within a server session.

Note on streaming:
  LlamaIndex's CondensePlusContextChatEngine supports stream_chat() which
  returns a StreamingAgentChatResponse with a response_gen generator.
  We use this when ColBERT is OFF.

  When ColBERT is ON, the pipeline bypasses the chat engine and calls
  Settings.llm.complete() directly (see qa_service.py). LlamaIndex LLMs
  support stream_complete() for streaming. We use that path here.
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Optional, Tuple, List

from llama_index.core import Settings
from llama_index.core.memory import ChatMemoryBuffer

from app.llm.llm_client import get_llm, get_embed_model
from app.retrieval.query_router import QueryMode
from app.config import USE_COLBERT, TOP_K_CHUNKS, TOP_K_RERANK
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── In-process session cache ──────────────────────────────────────────────────
# Key: (repo_id, chat_id) → (chat_engine, memory, last_mode)
# This lives as long as the FastAPI process is running.
# On server restart, LlamaIndex rebuilds from ChromaDB (fast, no re-embedding).
_session_cache: dict = {}


def _get_or_init_session(repo_id: str, chat_id: str):
    """Return cached (chat_engine, memory, last_mode) or (None, None, None)."""
    return _session_cache.get((repo_id, chat_id), (None, None, None))


def _save_session(repo_id: str, chat_id: str, engine, memory, mode):
    _session_cache[(repo_id, chat_id)] = (engine, memory, mode)


def _ensure_llamaindex():
    if Settings.llm is None:
        Settings.llm = get_llm()
    if Settings.embed_model is None:
        Settings.embed_model = get_embed_model()


async def stream_chat_response(
    query: str,
    index_name: str,
    repo_id: str,
    chat_id: str,
    supabase=None,  # Supabase client for memory rehydration
) -> AsyncGenerator[str, None]:
    """
    SSE generator for /chat/{chat_id}/message/stream.

    Yields:
        data: {"type": "token", "content": "..."}\\n\\n     (one per token)
        data: {"type": "metadata", ...}\\n\\n               (after full response)
        data: {"type": "done"}\\n\\n                        (stream ended successfully)
        data: {"type": "error", "message": "..."}\\n\\n     (stream ended with error — terminal)

    CONTRACT: "error" events are TERMINAL — no "done" is emitted after an error.
    This makes the frontend state machine unambiguous: either the stream ends with
    "done" (success) or "error" (failure), never both.

    MEMORY FIX: If in-process cache is empty (e.g., after server restart),
    rehydrates chat memory from Supabase prior messages before running the query.

    Internally uses the same dual-mode routing as qa_service.handle_user_query()
    but with streaming output.
    """
    _ensure_llamaindex()

    t_start = time.time()
    full_response = ""
    retrieved_files = []
    query_mode_value = "code_lookup"
    t_retrieval_ms = 0
    t_llm_ms = 0
    error_occurred = False  # Track whether we've already emitted an error

    try:
        # ── Load indexes ───────────────────────────────────────────────────
        from app.services.qa_service import _get_indexes
        from app.retrieval.query_router import classify_query
        from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT

        vector_index, bm25_retriever = await asyncio.get_event_loop().run_in_executor(
            None, _get_indexes, index_name
        )

        # ── Get/create memory with rehydration ─────────────────────────────
        # MEMORY FIX: Rehydrate from Supabase if in-process cache is empty
        from api.services import supabase_service
        
        chat_engine, memory, last_mode = _get_or_init_session(repo_id, chat_id)
        if memory is None:
            memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
            
            # Rehydrate from Supabase if this is the first access after restart
            try:
                prior_messages = supabase_service.get_messages_for_chat(supabase, chat_id)
                for msg in prior_messages:
                    # Reconstruct (role, content) pairs from DB
                    if msg.get("role") and msg.get("content"):
                        memory.put({
                            "role": msg["role"],
                            "content": msg["content"],
                        })
                logger.info(f"Rehydrated chat {chat_id} with {len(prior_messages)} prior messages from Supabase.")
            except Exception as rehydrate_err:
                logger.warning(f"Failed to rehydrate memory from Supabase: {rehydrate_err}")
                # Continue anyway with empty memory

        # ── Route query ────────────────────────────────────────────────────
        query_mode = await asyncio.get_event_loop().run_in_executor(
            None, classify_query, query
        )
        query_mode_value = query_mode.value

        # ── Retrieve nodes (for metadata + ColBERT path) ───────────────────
        t_ret_start = time.time()

        from llama_index.core.retrievers import QueryFusionRetriever
        from llama_index.core import QueryBundle

        if query_mode == QueryMode.CODE_LOOKUP and bm25_retriever is not None:
            retriever = QueryFusionRetriever(
                retrievers=[bm25_retriever, vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS)],
                similarity_top_k=TOP_K_CHUNKS,
                num_queries=1,
                mode="reciprocal_rerank",
                use_async=False,
            )
        else:
            retriever = vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS + 5)

        raw_nodes = await asyncio.get_event_loop().run_in_executor(
            None, retriever.retrieve, query
        )
        t_retrieval_ms = int((time.time() - t_ret_start) * 1000)

        # ── ColBERT reranking ──────────────────────────────────────────────
        if USE_COLBERT and raw_nodes:
            from app.retrieval.reranker import rerank_with_colbert
            reranked_nodes = await asyncio.get_event_loop().run_in_executor(
                None, rerank_with_colbert, query, raw_nodes, TOP_K_RERANK
            )
        else:
            reranked_nodes = sorted(raw_nodes, key=lambda n: n.score or 0.0, reverse=True)[:TOP_K_RERANK]

        # Build retrieved files list for metadata event
        retrieved_files = [
            {"path": n.node.metadata.get("path", "unknown"), "score": round(float(n.score or 0.0), 4)}
            for n in reranked_nodes
        ]

        # ── Build context string ───────────────────────────────────────────
        context_str = "\n\n".join([
            f"[{n.node.metadata.get('path', 'unknown')}]\n{n.node.get_content()}"
            for n in reranked_nodes
        ])

        system_prompt = (
            CODE_LOOKUP_PROMPT
            if query_mode == QueryMode.CODE_LOOKUP
            else ARCHITECTURAL_PROMPT
        )

        # ── Memory: get history ────────────────────────────────────────────
        try:
            history_msgs = memory.get()
            history_str = ""
            for msg in history_msgs[-6:]:  # last 3 turns
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    history_str += f"{role.upper()}: {content}\n"
        except Exception:
            history_str = ""

        full_prompt = (
            f"{system_prompt}\n\n"
            f"{'CONVERSATION HISTORY:' + chr(10) + history_str if history_str else ''}"
            f"Context:\n{context_str}\n\n"
            f"Question: {query}\n\nAnswer:"
        )

        # ── Stream LLM response ────────────────────────────────────────────
        t_llm_start = time.time()

        # stream_complete is available on all LlamaIndex LLM wrappers
        # (Ollama, Groq, Gemini, OpenAI all support it)
        stream_response = await asyncio.get_event_loop().run_in_executor(
            None, Settings.llm.stream_complete, full_prompt
        )

        # stream_response is a generator of CompletionResponseStreamChunk
        for chunk in stream_response:
            delta = chunk.delta or ""
            if delta:
                full_response += delta
                yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
                # Small yield to let the event loop breathe
                await asyncio.sleep(0)

        t_llm_ms = int((time.time() - t_llm_start) * 1000)

        # ── Update memory ──────────────────────────────────────────────────
        try:
            memory.put({"role": "user", "content": query})
            memory.put({"role": "assistant", "content": full_response})
            _save_session(repo_id, chat_id, None, memory, query_mode)
        except Exception as mem_err:
            logger.warning(f"Memory update failed: {mem_err}")

        t_total_ms = int((time.time() - t_start) * 1000)

        # ── Metadata event ─────────────────────────────────────────────────
        metadata = {
            "type": "metadata",
            "query_mode": query_mode_value,
            "retrieved_files": retrieved_files,
            "latency_retrieval_ms": t_retrieval_ms,
            "latency_llm_ms": t_llm_ms,
            "latency_total_ms": t_total_ms,
        }
        yield f"data: {json.dumps(metadata)}\n\n"
        
        # ── Emit done (success) ─────────────────────────────────────────────
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error(f"Streaming chat error: {e}", exc_info=True)
        error_occurred = True
        # Emit error as TERMINAL — no done follows
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    # Note: finally block deliberately removed to make error truly terminal
    # If no error occurred, we already emitted "done" above.
    # If an error occurred, we emit "error" and stop.
    return


async def get_full_response_for_persistence(
    query: str,
    index_name: str,
    repo_id: str,
    chat_id: str,
) -> Tuple[str, str, List[dict], int]:
    """
    Non-streaming version — used when we need to persist to DB
    but don't need to stream to client.

    Returns (response_str, query_mode, retrieved_files, latency_ms)
    """
    _ensure_llamaindex()

    from app.services.qa_service import handle_user_query

    chat_engine, memory, last_mode = _get_or_init_session(repo_id, chat_id)

    t_start = time.time()
    response_str, new_engine, new_memory, query_mode = await asyncio.get_event_loop().run_in_executor(
        None,
        handle_user_query,
        query,
        index_name,
        chat_engine,
        memory,
        last_mode,
    )
    latency_ms = int((time.time() - t_start) * 1000)

    _save_session(repo_id, chat_id, new_engine, new_memory, query_mode)

    return response_str, query_mode.value, [], latency_ms
