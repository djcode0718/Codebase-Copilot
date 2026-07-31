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


_FOLLOWUP_SUGGESTION_PROMPT = """You are helping a developer understand a codebase.
Based on the developer's question and the AI's response below, suggest exactly 3-4 natural follow-up questions that the developer might want to ask next.

Rules:
- Make them logical next steps / deeper questions based on the conversation
- Be specific to the codebase details mentioned in the response (e.g. classes, functions, files)
- Keep each question short (under 10 words)
- No numbering, no bullets — just the question text, one per line
- Make sure they end with a question mark

Developer Question: {query}
AI Response: {response}

Output exactly 3-4 follow-up questions, one per line, nothing else."""


def _default_followup_suggestions() -> List[str]:
    return [
        "Can you show me where this is implemented?",
        "Are there any tests for this code?",
        "What are the parameters/options available?",
    ]


async def _generate_followup_suggestions(query: str, response_text: str) -> List[str]:
    """Generates 3-4 dynamic follow-up questions based on the query and response."""
    from llama_index.core import Settings
    from app.llm.llm_client import get_llm

    if Settings.llm is None:
        Settings.llm = get_llm()

    prompt = _FOLLOWUP_SUGGESTION_PROMPT.format(query=query, response=response_text[:3000])

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, Settings.llm.complete, prompt
        )
        raw = str(response).strip()
        questions = [q.strip() for q in raw.split("\n") if q.strip()]
        # Filter out invalid questions or preambles
        questions = [q for q in questions if q.endswith("?")][:4]
        if not questions:
            questions = _default_followup_suggestions()
        return questions
    except Exception as e:
        logger.warning(f"Failed to generate follow-up suggestions: {e}")
        return _default_followup_suggestions()


async def stream_chat_response(
    query: str,
    index_name: str,
    repo_id: str,
    chat_id: str,
) -> AsyncGenerator[str, None]:
    """
    SSE generator for /chat/{chat_id}/message/stream.

    Yields:
        data: {"type": "token", "content": "..."}\\n\\n     (one per token)
        data: {"type": "metadata", ...}\\n\\n               (after full response)
        data: {"type": "done"}\\n\\n
        data: {"type": "error", "message": "..."}\\n\\n     (on failure)

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

    try:
        # ── Load indexes ───────────────────────────────────────────────────
        from app.services.qa_service import _get_indexes
        from app.retrieval.query_router import classify_query
        from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT

        vector_index, bm25_retriever = await asyncio.get_event_loop().run_in_executor(
            None, _get_indexes, index_name
        )

        # ── Get/create memory ──────────────────────────────────────────────
        chat_engine, memory, last_mode = _get_or_init_session(repo_id, chat_id)
        if memory is None:
            memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

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

        # ── Generate dynamic follow-up suggestions ─────────────────────────
        followup_questions = await _generate_followup_suggestions(query, full_response)
        yield f"data: {json.dumps({'type': 'suggestions', 'questions': followup_questions})}\n\n"

    except Exception as e:
        logger.error(f"Streaming chat error: {e}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    finally:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # Return full_response and metadata for DB persistence
    # (caller can access via the returned values if needed)
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
