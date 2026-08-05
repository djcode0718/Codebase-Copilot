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
import time
from typing import AsyncGenerator, Optional, Tuple, List

from llama_index.core import Settings
from llama_index.core.memory import ChatMemoryBuffer

from app.llm.llm_client import get_llm, get_embed_model
from app.retrieval.query_router import QueryMode
from app.config import (
    USE_COLBERT,
    TOP_K_CHUNKS,
    TOP_K_RERANK,
    LLM_PROVIDER,
    GROQ_API_KEY,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    STREAM_FIRST_TOKEN_TIMEOUT_SECONDS,
    STREAM_FIRST_TOKEN_FALLBACK_TEXT,
)
from app.utils.logger import get_logger
from api.services.chat_stream_utils import to_sse_data, safe_chat_error_message

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


def _build_fallback_llms() -> List[Tuple[str, object]]:
    """Build fallback LLM candidates in priority order, excluding the active provider."""
    active = (LLM_PROVIDER or "").lower()

    if active == "groq":
        providers_order = ["gemini", "openai", "ollama"]
    elif active == "openai":
        providers_order = ["gemini", "groq", "ollama"]
    elif active == "gemini":
        providers_order = ["groq", "openai", "ollama"]
    else:
        providers_order = ["gemini", "groq", "openai", "ollama"]

    candidates: List[Tuple[str, object]] = []
    for provider in providers_order:
        try:
            if provider == "ollama":
                from llama_index.llms.ollama import Ollama
                candidates.append(
                    (
                        "ollama",
                        Ollama(
                            model=OLLAMA_LLM_MODEL,
                            base_url=OLLAMA_BASE_URL,
                            request_timeout=120.0,
                        ),
                    )
                )
            elif provider == "groq" and GROQ_API_KEY:
                from llama_index.llms.groq import Groq
                candidates.append(("groq", Groq(model="llama-3.1-8b-instant", api_key=GROQ_API_KEY)))
            elif provider == "openai" and OPENAI_API_KEY:
                from llama_index.llms.openai import OpenAI
                candidates.append(("openai", OpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)))
            elif provider == "gemini" and GEMINI_API_KEY:
                from llama_index.llms.gemini import Gemini
                candidates.append(("gemini", Gemini(model="models/gemini-flash-latest", api_key=GEMINI_API_KEY)))
        except Exception as build_err:
            logger.warning(f"Skipping fallback provider '{provider}': {build_err}")

    return candidates


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

_NO_MATCH_CODE_LOOKUP_RESPONSE = (
    "I couldn't find that in the retrieved code. "
    "Try rephrasing or asking about a specific file or function."
)

_REPO_INTENT_KEYWORDS = {
    "repo", "repository", "code", "file", "module", "class", "function", "method",
    "bug", "error", "traceback", "api", "endpoint", "schema", "table", "query",
    "sql", "migration", "test", "pytest", "frontend", "backend", "service", "router",
    "model", "component", "typescript", "python", "javascript", "java", "go", "rust",
    "c#", "c++", ".py", ".ts", ".tsx", ".js", ".jsx",
}


def _repo_focused_rephrase_suggestions() -> List[str]:
    """Guided fallback suggestions for out-of-scope or invalid repository questions."""
    return [
        "Can you ask about a specific file in this repository?",
        "Which function or class should we inspect first?",
        "Can I get a quick map of the main folders?",
    ]


def _is_no_match_code_lookup_response(response_text: str) -> bool:
    text = (response_text or "").strip().lower()
    return text.startswith(_NO_MATCH_CODE_LOOKUP_RESPONSE.lower())


def _looks_repository_intent(query: str) -> bool:
    text = (query or "").strip().lower()
    if not text:
        return False

    if any(tok in text for tok in _REPO_INTENT_KEYWORDS):
        return True

    # Code-ish hints that usually indicate repository intent.
    return any(marker in text for marker in ("/", "\\", "::", "()", "{", "}"))


def _should_force_no_match(query: str, top_score: float) -> bool:
    """Short-circuit clearly out-of-scope prompts to the strict no-match response."""
    if _looks_repository_intent(query):
        return False
    # Irrelevant prompts should not proceed to full LLM synthesis.
    return top_score < 0.7


def _build_retriever(query_mode, vector_index, bm25_retriever):
    from llama_index.core.retrievers import QueryFusionRetriever

    if query_mode == QueryMode.CODE_LOOKUP and bm25_retriever is not None:
        return QueryFusionRetriever(
            retrievers=[bm25_retriever, vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS)],
            similarity_top_k=TOP_K_CHUNKS,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
        )

    return vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS + 5)


async def _retrieve_nodes(retriever, resolved_query: str):
    return await asyncio.get_event_loop().run_in_executor(None, retriever.retrieve, resolved_query)


async def _rerank_nodes(resolved_query: str, raw_nodes):
    if USE_COLBERT and raw_nodes:
        from app.retrieval.reranker import rerank_with_colbert

        return await asyncio.get_event_loop().run_in_executor(
            None, rerank_with_colbert, resolved_query, raw_nodes, TOP_K_RERANK
        )

    return sorted(raw_nodes, key=lambda n: n.score or 0.0, reverse=True)[:TOP_K_RERANK]


def _build_retrieved_files(reranked_nodes) -> List[dict]:
    return [
        {"path": n.node.metadata.get("path", "unknown"), "score": round(float(n.score or 0.0), 4)}
        for n in reranked_nodes
    ]


def _build_context_str(reranked_nodes) -> str:
    return "\n\n".join([
        f"[{n.node.metadata.get('path', 'unknown')}]\n{n.node.get_content()}"
        for n in reranked_nodes
    ])


def _build_history_str(memory) -> str:
    try:
        history_msgs = memory.get()
        history_str = ""
        for msg in history_msgs[-6:]:  # last 3 turns
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                history_str += f"{role.upper()}: {content}\n"
        return history_str
    except Exception:
        return ""


def _build_full_prompt(
    system_prompt: str,
    memory_context: Optional[str],
    history_str: str,
    context_str: str,
    resolved_query: str,
) -> str:
    return (
        f"{system_prompt}\n\n"
        f"{'REPOSITORY MEMORY:' + chr(10) + memory_context + chr(10) if memory_context else ''}"
        f"{'CONVERSATION HISTORY:' + chr(10) + history_str if history_str else ''}"
        f"Context:\n{context_str}\n\n"
        f"Question: {resolved_query}\n\nAnswer:"
    )


def _build_metadata_event(
    query_mode_value: str,
    retrieved_files: List[dict],
    t_retrieval_ms: int,
    t_llm_ms: int,
    t_total_ms: int,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> dict:
    return {
        "type": "metadata",
        "query_mode": query_mode_value,
        "retrieved_files": retrieved_files,
        "latency_retrieval_ms": t_retrieval_ms,
        "latency_llm_ms": t_llm_ms,
        "latency_total_ms": t_total_ms,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
    }


def _provider_unavailable_response() -> str:
    return (
        "I could not generate a full answer right now because the model providers are temporarily "
        "rate-limited or unavailable. Please retry in a moment, or ask a narrower question about "
        "a specific file, function, class, or module."
    )


class StreamFirstTokenTimeoutError(TimeoutError):
    """Raised when streaming never produces a first token within guard time."""


def _first_token_fallback_response() -> str:
    if STREAM_FIRST_TOKEN_FALLBACK_TEXT:
        return STREAM_FIRST_TOKEN_FALLBACK_TEXT
    return _provider_unavailable_response()


async def _stream_llm_response_with_guard(
    full_prompt: str,
    timeout_seconds: Optional[float] = None,
) -> AsyncGenerator[str, None]:
    """Yield tokens from LLM stream with a bounded first-token wait."""
    timeout = STREAM_FIRST_TOKEN_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    timeout = max(float(timeout), 0.1)

    stream = _stream_llm_response(full_prompt)
    try:
        try:
            first_delta = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise StreamFirstTokenTimeoutError(
                f"First token timeout after {timeout:.2f}s"
            ) from exc
        except StopAsyncIteration:
            return

        yield first_delta
        async for delta in stream:
            yield delta
    finally:
        await stream.aclose()


async def _resolve_query_mode(query: str, memory, classify_query):
    from app.services.qa_service import resolve_ambiguous_query

    resolved_query = await asyncio.get_event_loop().run_in_executor(
        None, resolve_ambiguous_query, query, memory
    )
    if resolved_query != query:
        logger.info(f"Resolved context-aware streaming query: '{resolved_query}'")

    query_mode = await asyncio.get_event_loop().run_in_executor(
        None, classify_query, resolved_query
    )
    return resolved_query, query_mode


def _build_no_match_events(
    *,
    t_start: float,
    retrieved_files: List[dict],
    t_retrieval_ms: int,
) -> List[str]:
    full_response = _NO_MATCH_CODE_LOOKUP_RESPONSE
    query_mode_value = QueryMode.CODE_LOOKUP.value
    events: List[str] = [to_sse_data({"type": "token", "content": full_response})]

    t_total_ms = int((time.time() - t_start) * 1000)
    metadata = _build_metadata_event(
        query_mode_value,
        retrieved_files,
        t_retrieval_ms,
        0,
        t_total_ms,
        None,
        None,
    )
    events.append(to_sse_data(metadata))
    events.append(to_sse_data({"type": "suggestions", "questions": _repo_focused_rephrase_suggestions()}))
    return events


async def _stream_llm_response(full_prompt: str) -> AsyncGenerator[str, None]:
    from app.services.llm_fallback import stream_with_fallback

    def _coerce_text(value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _pick_attr_or_key(chunk_obj, field: str):
        if isinstance(chunk_obj, dict):
            return chunk_obj.get(field)
        return getattr(chunk_obj, field, None)

    def _extract_chunk_delta(chunk_obj, last_cumulative: str) -> Tuple[str, str]:
        # Preferred token-like delta payload.
        delta = _coerce_text(_pick_attr_or_key(chunk_obj, "delta"))
        if delta:
            return delta, last_cumulative

        # Some providers expose cumulative content instead of per-token deltas.
        cumulative_text = ""
        for field in ("text", "response", "content"):
            cumulative_text = _coerce_text(_pick_attr_or_key(chunk_obj, field))
            if cumulative_text:
                break

        if cumulative_text:
            if last_cumulative and cumulative_text.startswith(last_cumulative):
                return cumulative_text[len(last_cumulative):], cumulative_text
            return cumulative_text, cumulative_text

        # Fallback: plain string chunk.
        if isinstance(chunk_obj, str):
            return chunk_obj, last_cumulative

        return "", last_cumulative

    stream_response = stream_with_fallback(full_prompt)
    last_cumulative_text = ""
    async for chunk in stream_response:
        delta, last_cumulative_text = _extract_chunk_delta(chunk, last_cumulative_text)
        if not delta:
            continue
        yield delta
        await asyncio.sleep(0)


def _persist_memory_turn(repo_id: str, chat_id: str, memory, query: str, full_response: str, query_mode):
    from llama_index.core.base.llms.types import ChatMessage

    memory.put(ChatMessage(role="user", content=query))
    memory.put(ChatMessage(role="assistant", content=full_response))
    _save_session(repo_id, chat_id, None, memory, query_mode)


async def _emit_followup_events(full_response: str, resolved_query: str):
    if _is_no_match_code_lookup_response(full_response):
        followup_questions = _repo_focused_rephrase_suggestions()
    else:
        followup_questions = await _generate_followup_suggestions(resolved_query, full_response)
    yield to_sse_data({"type": "suggestions", "questions": followup_questions})


async def _load_indexes(index_name: str):
    from app.services.qa_service import _get_indexes

    return await asyncio.get_event_loop().run_in_executor(None, _get_indexes, index_name)


def _get_or_create_memory(repo_id: str, chat_id: str):
    _chat_engine, memory, _last_mode = _get_or_init_session(repo_id, chat_id)
    if memory is None:
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
    return memory


async def _retrieve_ranked_nodes(query_mode, vector_index, bm25_retriever, resolved_query: str):
    t_ret_start = time.time()
    retriever = _build_retriever(query_mode, vector_index, bm25_retriever)
    raw_nodes = await _retrieve_nodes(retriever, resolved_query)
    reranked_nodes = await _rerank_nodes(resolved_query, raw_nodes)
    t_retrieval_ms = int((time.time() - t_ret_start) * 1000)
    return reranked_nodes, t_retrieval_ms


def _select_system_prompt(query_mode, code_lookup_prompt: str, architectural_prompt: str) -> str:
    return code_lookup_prompt if query_mode == QueryMode.CODE_LOOKUP else architectural_prompt


async def _prepare_stream_prompt(
    *,
    query: str,
    index_name: str,
    repo_id: str,
    chat_id: str,
    memory_context: Optional[str],
):
    from app.retrieval.query_router import classify_query
    from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT

    vector_index, bm25_retriever = await _load_indexes(index_name)
    memory = _get_or_create_memory(repo_id, chat_id)

    resolved_query, query_mode = await _resolve_query_mode(query, memory, classify_query)
    reranked_nodes, t_retrieval_ms = await _retrieve_ranked_nodes(
        query_mode,
        vector_index,
        bm25_retriever,
        resolved_query,
    )
    retrieved_files = _build_retrieved_files(reranked_nodes)
    context_str = _build_context_str(reranked_nodes)
    history_str = _build_history_str(memory)

    system_prompt = _select_system_prompt(query_mode, CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT)
    full_prompt = _build_full_prompt(system_prompt, memory_context, history_str, context_str, resolved_query)

    return {
        "memory": memory,
        "resolved_query": resolved_query,
        "query_mode": query_mode,
        "reranked_nodes": reranked_nodes,
        "retrieved_files": retrieved_files,
        "t_retrieval_ms": t_retrieval_ms,
        "full_prompt": full_prompt,
    }


def _default_followup_suggestions() -> List[str]:
    return [
        "Can you show me where this is implemented?",
        "Are there any tests for this code?",
        "What are the parameters/options available?",
    ]


async def _generate_followup_suggestions(query: str, response_text: str) -> List[str]:
    """Generates 3-4 dynamic follow-up questions based on the query and response."""
    from app.services.llm_fallback import generate_with_fallback

    prompt = _FOLLOWUP_SUGGESTION_PROMPT.format(query=query, response=response_text[:3000])

    try:
        raw = await generate_with_fallback(prompt)
        questions = [q.strip() for q in raw.split("\n") if q.strip()]

        # Clean prefixes like "1. ", "-", "*", "Q:"
        cleaned = []
        for q in questions:
            q = q.lstrip("1234567890.-* \t")
            if q.lower().startswith("question"):
                q = q.split(":", 1)[-1].strip()
            if len(q) > 10:
                if not q.endswith("?"):
                    q += "?"
                cleaned.append(q)

        if cleaned:
            return cleaned[:3]
        return _default_followup_suggestions()
    except Exception as e:
        logger.warning(f"Failed to generate follow-up suggestions: {e}")
        return _default_followup_suggestions()


async def stream_chat_response(
    query: str,
    index_name: str,
    repo_id: str,
    chat_id: str,
    memory_context: Optional[str] = None,
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
    llm_provider = None
    llm_model = None

    try:
        prep = await _prepare_stream_prompt(
            query=query,
            index_name=index_name,
            repo_id=repo_id,
            chat_id=chat_id,
            memory_context=memory_context,
        )
        memory = prep["memory"]
        resolved_query = prep["resolved_query"]
        query_mode = prep["query_mode"]
        reranked_nodes = prep["reranked_nodes"]
        retrieved_files = prep["retrieved_files"]
        t_retrieval_ms = prep["t_retrieval_ms"]
        full_prompt = prep["full_prompt"]
        query_mode_value = query_mode.value

        top_score = max((float(n.score or 0.0) for n in reranked_nodes), default=0.0)
        if _should_force_no_match(query, top_score):
            full_response = _NO_MATCH_CODE_LOOKUP_RESPONSE
            for evt in _build_no_match_events(
                t_start=t_start,
                retrieved_files=retrieved_files,
                t_retrieval_ms=t_retrieval_ms,
            ):
                yield evt
            return


        # ── Stream LLM response ────────────────────────────────────────────
        t_llm_start = time.time()

        try:
            from app.services.llm_fallback import get_last_llm_usage, reset_last_llm_usage
            reset_last_llm_usage()
            async for delta in _stream_llm_response_with_guard(full_prompt):
                full_response += delta
                yield to_sse_data({'type': 'token', 'content': delta})

            # Guarantee the UI receives at least one token event.
            if not full_response.strip():
                full_response = _first_token_fallback_response()
                yield to_sse_data({'type': 'token', 'content': full_response})

            usage = get_last_llm_usage()
            llm_provider = usage.get("provider")
            llm_model = usage.get("model")
        except StreamFirstTokenTimeoutError as timeout_err:
            logger.warning(f"LLM stream startup timeout; sending fallback token: {timeout_err}")
            full_response = _first_token_fallback_response()
            yield to_sse_data({'type': 'token', 'content': full_response})
        except Exception as llm_err:
            logger.warning(f"LLM streaming failed; falling back to safe assistant response: {llm_err}")
            full_response = _first_token_fallback_response()
            yield to_sse_data({'type': 'token', 'content': full_response})

        t_llm_ms = int((time.time() - t_llm_start) * 1000)

        # ── Update memory ──────────────────────────────────────────────────
        try:
            _persist_memory_turn(repo_id, chat_id, memory, query, full_response, query_mode)
        except Exception as mem_err:
            logger.warning(f"Memory update failed: {mem_err}")

        t_total_ms = int((time.time() - t_start) * 1000)

        # ── Metadata event ─────────────────────────────────────────────────
        metadata = _build_metadata_event(
            query_mode_value,
            retrieved_files,
            t_retrieval_ms,
            t_llm_ms,
            t_total_ms,
            llm_provider,
            llm_model,
        )
        yield to_sse_data(metadata)

        async for suggestions_event in _emit_followup_events(full_response, resolved_query):
            yield suggestions_event

    except Exception as e:
        logger.error(f"Streaming chat error: {e}", exc_info=True)
        yield to_sse_data({'type': 'error', 'message': safe_chat_error_message(e, include_rate_limit=True)})

    finally:
        yield to_sse_data({'type': 'done'})

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
