"""
api/services/chat_service.py
─────────────────────────────
Manages chat queries with a repository, supporting both streaming (SSE) and non-streaming modes.

Non-streaming queries:
  `get_full_response_for_persistence` wraps `app/services/qa_service.handle_user_query()`.

Streaming queries:
  `stream_chat_response` does NOT call `app/services/qa_service.handle_user_query()`. Instead, 
  it runs a dedicated local retrieval, routing, and prompt assembly loop using the local 
  `_prepare_stream_prompt` implementation, and streams Server-Sent Events (SSE) using LLM streaming APIs.

Session state (chat_engine + memory) is cached in-process per (repo_id, chat_id)
so multi-turn conversation works correctly within a server session.
"""

import asyncio
import time
from typing import AsyncGenerator, Optional, Tuple, List, Dict, Any

from llama_index.core import Settings
from llama_index.core.memory import ChatMemoryBuffer

from app.llm.llm_client import configure_llamaindex_settings
from app.retrieval.query_router import QueryMode, is_general_knowledge_or_preference_query
from app.config import (
    USE_COLBERT,
    TOP_K_CHUNKS,
    TOP_K_RERANK,
    LLM_PROVIDER,
    STREAM_FIRST_TOKEN_TIMEOUT_SECONDS,
    STREAM_FIRST_TOKEN_FALLBACK_TEXT,
)
from app.utils.logger import get_logger
from app.llm.prompts import CHAT_FOLLOWUP_SUGGESTION_PROMPT
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
    # Force app-configured providers every request path to avoid fallback to
    # unintended library defaults when Settings are pre-populated.
    configure_llamaindex_settings()


def _build_fallback_llms() -> List[Tuple[str, object]]:
    """Build fallback LLM candidates from configured providers, excluding active provider."""
    from app.services.model_manager import create_llm_client, get_available_model_specs

    active = (LLM_PROVIDER or "").strip().lower()
    candidates: List[Tuple[str, object]] = []
    for spec in get_available_model_specs():
        if spec.provider == active:
            continue
        try:
            candidates.append((spec.provider, create_llm_client(spec)))
        except Exception as build_err:
            logger.warning(f"Skipping fallback provider '{spec.provider}/{spec.model_name}': {build_err}")

    return candidates


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
    # Config / auth / provider terms — queries about these clearly target the codebase
    "provider", "configure", "configured", "configuration", "authenticate",
    "authenticated", "authentication", "credential", "credentials", "secret",
    "token", "key", "env", "environment", "setting", "settings",
    "llm", "embedding", "vector", "index", "retrieval", "pipeline",
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


def _should_force_no_match(query: str, top_score: float, use_colbert: bool = True) -> bool:
    """Short-circuit clearly out-of-scope prompts to the strict no-match response.

    Score-scale contract:
    - When use_colbert=True:  top_score is CrossEncoder sigmoid-normalized → (0, 1).
        Relevant queries score ≥ 0.60; out-of-scope queries cluster at ≈ 0.50.
        Threshold 0.60 confirmed by 7-query calibration (4 answerable + 3 OOS).
    - When use_colbert=False: top_score is an RRF score in [0, ~0.10].
        RRF scores are never meaningful as an out-of-scope signal (max ≈ 0.033
        even for on-topic queries). Skip the score check entirely.
    """
    if _looks_repository_intent(query):
        return False
    if not use_colbert:
        # RRF scores max at ~0.03 regardless of relevance — score threshold is
        # meaningless here; rely solely on _looks_repository_intent.
        return False
    # CrossEncoder sigmoid scores: out-of-scope queries ≈ 0.50, relevant ≥ 0.60.
    return top_score < 0.60


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


def _to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_line_range(metadata: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    start = _to_int_or_none(
        metadata.get("line_start")
        or metadata.get("start_line")
        or metadata.get("start")
        or metadata.get("line")
    )
    end = _to_int_or_none(
        metadata.get("line_end")
        or metadata.get("end_line")
        or metadata.get("end")
    )
    if start is not None and end is None:
        end = start
    if start is None and end is not None:
        start = end
    if start is not None and end is not None and end < start:
        start, end = end, start
    return start, end


def _build_retrieved_files(reranked_nodes) -> List[dict]:
    payload: List[dict] = []
    for node_with_score in reranked_nodes:
        metadata = getattr(node_with_score.node, "metadata", {}) or {}
        line_start, line_end = _extract_line_range(metadata)
        payload.append({
            "path": metadata.get("path", "unknown"),
            "score": round(float(node_with_score.score or 0.0), 4),
            "line_start": line_start,
            "line_end": line_end,
        })
    return payload


def _build_context_str(reranked_nodes) -> str:
    return "\n\n".join([
        f"[{n.node.metadata.get('path', 'unknown')}]\n{n.node.get_content()}"
        for n in reranked_nodes
    ])


def _build_history_str(memory) -> str:
    try:
        history_msgs = memory.get()
        history_str = ""
        for msg in history_msgs[-40:]:
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


async def _recover_from_stream_failure(full_prompt: str, llm_err: Exception) -> Tuple[str, str]:
    """Try non-stream generation when streaming startup fails before first token."""
    from app.services.llm_fallback import generate_with_fallback, get_resilient_llm

    try:
        # Fast async recovery first.
        recovered = await asyncio.wait_for(generate_with_fallback(full_prompt), timeout=15)
        recovered_text = (recovered or "").strip()
        if recovered_text:
            logger.info("Recovered answer via non-stream fallback after streaming failure.")
            return recovered_text, "non_stream_recovery"
    except Exception as recover_err:
        logger.warning(
            "Non-stream recovery failed after streaming failure (%s): %s",
            llm_err,
            recover_err,
        )

    try:
        # Some providers fail only on async paths; run sync completion in executor as backup.
        loop = asyncio.get_running_loop()

        def _sync_complete() -> str:
            llm = get_resilient_llm()
            result = llm.complete(full_prompt)
            return str(result).strip()

        recovered_sync = await asyncio.wait_for(loop.run_in_executor(None, _sync_complete), timeout=35)
        if recovered_sync:
            logger.info("Recovered answer via sync non-stream fallback after streaming failure.")
            return recovered_sync, "non_stream_recovery"
    except Exception as sync_recover_err:
        logger.warning(
            "Sync non-stream recovery failed after streaming failure (%s): %s",
            llm_err,
            sync_recover_err,
        )

    return _first_token_fallback_response(), "safe_fallback"


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
    from app.retrieval.query_router import _is_relationship_query
    from app.services.qa_service import resolve_ambiguous_query
    from app.llm.llm_client import configure_llamaindex_settings

    # First check: Run RELATIONSHIP check on the raw, original query
    if _is_relationship_query(query):
        logger.info("Raw query classified as RELATIONSHIP (bypassed rewriting)")
        return query, QueryMode.RELATIONSHIP

    # If not a relationship query, proceed with normal resolution & classification
    def _resolve_query_with_settings():
        configure_llamaindex_settings()
        return resolve_ambiguous_query(query, memory)

    def _classify_query_with_settings(resolved: str):
        configure_llamaindex_settings()
        return classify_query(resolved)

    resolved_query = await asyncio.get_event_loop().run_in_executor(
        None, _resolve_query_with_settings
    )
    if resolved_query != query:
        logger.info(f"Resolved context-aware streaming query: '{resolved_query}'")

    query_mode = await asyncio.get_event_loop().run_in_executor(
        None, _classify_query_with_settings, resolved_query
    )
    return resolved_query, query_mode


def _build_no_match_events(
    *,
    t_start: float,
    retrieved_files: List[dict],
    t_retrieval_ms: int,
    query_mode_value: str = QueryMode.CODE_LOOKUP.value,
) -> List[str]:
    full_response = _NO_MATCH_CODE_LOOKUP_RESPONSE
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
        # First try to get cumulative text from standard fields
        cumulative_text = ""
        for field in ("text", "response", "content"):
            cumulative_text = _coerce_text(_pick_attr_or_key(chunk_obj, field))
            if cumulative_text:
                break

        if cumulative_text:
            if last_cumulative and cumulative_text.startswith(last_cumulative):
                return cumulative_text[len(last_cumulative):], cumulative_text
            return cumulative_text, cumulative_text

        # Fallback to delta token-like payload
        delta = _coerce_text(_pick_attr_or_key(chunk_obj, "delta"))
        if delta:
            return delta, last_cumulative + delta

        # Fallback: plain string chunk
        if isinstance(chunk_obj, str):
            return chunk_obj, last_cumulative + chunk_obj

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


def _hydrate_memory(memory, persisted_history: Optional[List[Dict[str, Any]]]) -> bool:
    if not persisted_history:
        return False

    try:
        from llama_index.core.base.llms.types import ChatMessage

        hydrated = False
        for item in persisted_history:
            role = (item.get("role") or "").lower()
            content = (item.get("content") or "").strip()
            if role not in {"system", "user", "assistant"} or not content:
                continue
            memory.put(ChatMessage(role=role, content=content))
            hydrated = True
        return hydrated
    except Exception as e:
        logger.warning(f"Failed to hydrate chat memory from persisted history: {e}")
        return False


def _get_or_create_memory(repo_id: str, chat_id: str, persisted_history: Optional[List[Dict[str, Any]]] = None):
    _chat_engine, memory, _last_mode = _get_or_init_session(repo_id, chat_id)
    if memory is None:
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        if _hydrate_memory(memory, persisted_history):
            _save_session(repo_id, chat_id, None, memory, _last_mode)
    return memory


async def _retrieve_ranked_nodes(query_mode, vector_index, bm25_retriever, resolved_query: str):
    t_ret_start = time.time()
    retriever = _build_retriever(query_mode, vector_index, bm25_retriever)
    raw_nodes = await _retrieve_nodes(retriever, resolved_query)
    logger.debug("Retrieved %s raw nodes for streaming query_mode=%s", len(raw_nodes), query_mode.value)
    reranked_nodes = await _rerank_nodes(resolved_query, raw_nodes)
    logger.debug("Reranked nodes count=%s for streaming query", len(reranked_nodes))
    t_retrieval_ms = int((time.time() - t_ret_start) * 1000)
    logger.debug("Retrieval+rereank latency_ms=%s", t_retrieval_ms)
    return reranked_nodes, t_retrieval_ms


def _select_system_prompt(query_mode, code_lookup_prompt: str, architectural_prompt: str) -> str:
    return code_lookup_prompt if query_mode == QueryMode.CODE_LOOKUP else architectural_prompt


def _stream_early_response_payload(memory, query: str, response_str: str) -> dict:
    logger.debug("Returning streaming early response payload (response_length=%s)", len(response_str or ""))
    return {
        "memory": memory,
        "resolved_query": query,
        "query_mode": QueryMode.CODE_LOOKUP,
        "reranked_nodes": [],
        "retrieved_files": [],
        "t_retrieval_ms": 0,
        "full_prompt": "",
        "early_response": response_str,
    }


def _stream_prechecks(query: str, index_name: str, memory, is_cta_followup: bool) -> Optional[dict]:
    if is_cta_followup:
        return None

    from app.retrieval.query_router import detect_excluded_folder, detect_aggregation, check_superlative_intent

    excluded_folder = detect_excluded_folder(query)
    if excluded_folder:
        logger.info("Stream early exit: excluded folder referenced")
        err_msg = f"That folder ({excluded_folder}) is excluded from indexing (build/CI/dependency artifacts aren't indexed by default)."
        return _stream_early_response_payload(memory, query, err_msg)

    if detect_aggregation(query):
        logger.info("Stream early exit: aggregation query")
        from app.services.repo_stats_service import handle_aggregation_query

        response_str = handle_aggregation_query(query, index_name)
        return _stream_early_response_payload(memory, query, response_str)

    superlative_suggest = check_superlative_intent(query)
    if superlative_suggest:
        logger.info("Stream early exit: superlative action suggestion")
        import json

        return _stream_early_response_payload(memory, query, json.dumps(superlative_suggest))

    return None


def _relationship_prompt_payload(index_name: str, memory, resolved_query: str, query_mode: QueryMode) -> dict:
    from app.retrieval.query_router import extract_relationship_target
    from app.llm.prompts import RELATIONSHIP_PROMPT
    import os

    target = extract_relationship_target(resolved_query)
    logger.info("Stage -1: RELATIONSHIP query detected in stream. target=%s", target)
    refs = []
    if target:
        from app.config import INDEX_DIR

        graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
        logger.debug("Relationship graph lookup path for stream=%s", graph_path)
        if os.path.exists(graph_path):
            try:
                import json
                with open(graph_path, "r", encoding="utf-8") as gf:
                    graph = json.load(gf)
                refs = graph.get(target, [])
                if not refs:
                    for key, val in graph.items():
                        if key.lower() == target.lower():
                            refs = val
                            break
                logger.info("Relationship graph stream lookup returned %s references", len(refs))
            except Exception as ex:
                logger.warning(f"Failed to load relationship graph in stream: {ex}")
        else:
            logger.warning(f"Relationship graph file not found at {graph_path}")
    else:
        logger.info("Relationship target extraction returned None in stream")

    ref_list_str = "\n".join([f"- {r}" for r in refs]) if refs else "No references found."
    full_prompt = RELATIONSHIP_PROMPT.format(
        target_symbol=target or "unknown",
        references_list=ref_list_str,
    )

    return {
        "memory": memory,
        "resolved_query": resolved_query,
        "query_mode": query_mode,
        "reranked_nodes": [],
        "retrieved_files": [],
        "t_retrieval_ms": 0,
        "full_prompt": full_prompt,
    }


def _inject_arch_context_if_missing(query_mode, index_name: str, reranked_nodes, context_str: str) -> str:
    if query_mode != QueryMode.ARCHITECTURAL:
        return context_str

    retrieved_paths = {n.node.metadata.get("path", "") for n in reranked_nodes}
    if "_codebase_context" in retrieved_paths:
        logger.debug("ARCHITECTURAL mode already contains _codebase_context in top-k")
        return context_str

    try:
        import os as _os
        import chromadb as _chromadb
        from app.config import INDEX_DIR as _INDEX_DIR

        _chroma_path = _os.path.join(_INDEX_DIR, index_name, "chroma")
        _chroma_client = _chromadb.PersistentClient(path=_chroma_path)
        _chroma_collection = _chroma_client.get_or_create_collection(index_name)
        _ctx_results = _chroma_collection.get(
            where={"path": {"$eq": "_codebase_context"}},
            limit=2,
            include=["documents"],
        )
        if _ctx_results["documents"]:
            _injected = "\n\n".join(
                f"[_codebase_context]\n{doc}" for doc in _ctx_results["documents"]
            )
            logger.info(
                "ARCHITECTURAL stream prompt injected %s _codebase_context chunks",
                len(_ctx_results["documents"]),
            )
            return context_str + "\n\n" + _injected
    except Exception as _ctx_err:
        logger.warning(f"_codebase_context injection failed: {_ctx_err}")
    return context_str


async def _prepare_stream_prompt(
    *,
    query: str,
    index_name: str,
    repo_id: str,
    chat_id: str,
    memory_context: Optional[str],
    persisted_history: Optional[List[Dict[str, Any]]] = None,
    is_cta_followup: bool = False,
):
    from app.retrieval.query_router import classify_query
    from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT

    logger.info("Preparing stream prompt for repo=%s chat=%s", repo_id, chat_id)
    vector_index, bm25_retriever = await _load_indexes(index_name)
    logger.debug("Loaded stream indexes (bm25_available=%s)", bm25_retriever is not None)
    memory = _get_or_create_memory(repo_id, chat_id, persisted_history)
    logger.debug("Loaded/created stream memory (hydrated_history=%s)", bool(persisted_history))

    precheck = _stream_prechecks(query, index_name, memory, is_cta_followup)
    if precheck is not None:
        return precheck

    resolved_query, query_mode = await _resolve_query_mode(query, memory, classify_query)
    logger.info("Resolved stream query mode=%s", query_mode.value)

    if query_mode == QueryMode.RELATIONSHIP:
        return _relationship_prompt_payload(index_name, memory, resolved_query, query_mode)

    reranked_nodes, t_retrieval_ms = await _retrieve_ranked_nodes(
        query_mode,
        vector_index,
        bm25_retriever,
        resolved_query,
    )
    retrieved_files = _build_retrieved_files(reranked_nodes)
    context_str = _build_context_str(reranked_nodes)
    context_str = _inject_arch_context_if_missing(query_mode, index_name, reranked_nodes, context_str)

    history_str = _build_history_str(memory)

    system_prompt = _select_system_prompt(query_mode, CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT)
    full_prompt = _build_full_prompt(system_prompt, memory_context, history_str, context_str, resolved_query)
    logger.debug("Prepared stream prompt (query_mode=%s, prompt_length=%s)", query_mode.value, len(full_prompt))

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

    prompt = CHAT_FOLLOWUP_SUGGESTION_PROMPT.format(query=query, response=response_text[:3000])

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
    persisted_history: Optional[List[Dict[str, Any]]] = None,
    is_cta_followup: bool = False,
) -> AsyncGenerator[str, None]:
    """
    SSE generator for /chat/{chat_id}/message/stream.

    Yields:
        data: {"type": "token", "content": "..."}\n\n     (one per token)
        data: {"type": "metadata", ...}\n\n               (after full response)
        data: {"type": "done"}\n\n
        data: {"type": "error", "message": "..."}\n\n     (on failure)

    Internally, this does NOT call `app/services/qa_service.handle_user_query()`. Instead, it uses 
    the local `_prepare_stream_prompt` implementation to run its own routing, retrieval, 
    and prompt assembly loop, and streams the results.
    """
    _ensure_llamaindex()
    logger.info("Starting stream_chat_response repo_id=%s chat_id=%s", repo_id, chat_id)

    t_start = time.time()
    _state = {
        "full_response": "",
        "retrieved_files": [],
        "query_mode_value": "code_lookup",
        "t_retrieval_ms": 0,
        "t_llm_ms": 0,
        "llm_provider": None,
        "llm_model": None,
        "response_path": "safe_fallback",
    }
    full_response = _state["full_response"]
    retrieved_files = _state["retrieved_files"]
    query_mode_value = _state["query_mode_value"]
    t_retrieval_ms = _state["t_retrieval_ms"]
    t_llm_ms = _state["t_llm_ms"]
    llm_provider = _state["llm_provider"]
    llm_model = _state["llm_model"]
    response_path = _state["response_path"]

    def _terminal_events(
        *,
        text: str,
        query_mode: str,
        files: List[dict],
        retrieval_ms: int,
    ) -> List[str]:
        logger.debug(
            "Building terminal stream events (mode=%s, retrieval_ms=%s, files=%s, text_len=%s)",
            query_mode,
            retrieval_ms,
            len(files),
            len(text or ""),
        )
        t_total_ms = int((time.time() - t_start) * 1000)
        metadata = _build_metadata_event(
            query_mode_value=query_mode,
            retrieved_files=files,
            t_retrieval_ms=retrieval_ms,
            t_llm_ms=0,
            t_total_ms=t_total_ms,
            llm_provider=None,
            llm_model=None,
        )
        return [
            to_sse_data({'type': 'token', 'content': text}),
            to_sse_data(metadata),
            to_sse_data({"type": "suggestions", "questions": _repo_focused_rephrase_suggestions()}),
            to_sse_data({"type": "done"}),
        ]

    try:
        prep = await _prepare_stream_prompt(
            query=query,
            index_name=index_name,
            repo_id=repo_id,
            chat_id=chat_id,
            memory_context=memory_context,
            persisted_history=persisted_history,
            is_cta_followup=is_cta_followup,
        )
        memory = prep["memory"]
        resolved_query = prep["resolved_query"]
        query_mode = prep["query_mode"]
        reranked_nodes = prep["reranked_nodes"]
        retrieved_files = prep["retrieved_files"]
        t_retrieval_ms = prep["t_retrieval_ms"]
        full_prompt = prep["full_prompt"]
        query_mode_value = query_mode.value

        if "early_response" in prep:
            logger.info("Streaming exited early with deterministic response")
            early_resp = prep["early_response"]
            for evt in _terminal_events(text=early_resp, query_mode=query_mode_value, files=[], retrieval_ms=0):
                yield evt
            _persist_memory_turn(repo_id, chat_id, memory, query, early_resp, query_mode)
            return

        if is_general_knowledge_or_preference_query(query) or is_general_knowledge_or_preference_query(resolved_query):
            logger.info("Streaming no-match path triggered by out-of-scope detection")
            for evt in _build_no_match_events(
                t_start=t_start,
                retrieved_files=retrieved_files,
                t_retrieval_ms=t_retrieval_ms,
                query_mode_value=query_mode_value,
            ):
                yield evt
            return

        top_score = max((float(n.score or 0.0) for n in reranked_nodes), default=0.0)
        logger.debug("Streaming top reranked score=%.3f mode=%s", top_score, query_mode_value)

        # ── Low Confidence Check (Streaming) ──────────────────────────────────
        from app.retrieval.query_router import LOW_CONFIDENCE_SIMILARITY_THRESHOLD
        if top_score < LOW_CONFIDENCE_SIMILARITY_THRESHOLD:
            logger.info("Streaming low-confidence clarification path triggered")
            clarification = "Could you point me to a specific file, folder, or function? I want to search the right part of the repo."
            for evt in _terminal_events(
                text=clarification,
                query_mode=query_mode_value,
                files=retrieved_files,
                retrieval_ms=t_retrieval_ms,
            ):
                yield evt
            _persist_memory_turn(repo_id, chat_id, memory, query, clarification, query_mode)
            return
        # No-match guard: only applied for CODE_LOOKUP mode.
        # ARCHITECTURAL mode is designed for broad reasoning — CrossEncoder scores
        # for natural-language architecture queries are always low (sigmoid ≈ 0.50)
        # since the retrieved content is code, not natural language. Silencing those
        # queries defeats the purpose of ARCHITECTURAL mode.
        # RELATIONSHIP mode is handled separately above (returns before this point).
        if query_mode == QueryMode.CODE_LOOKUP and _should_force_no_match(query, top_score, use_colbert=USE_COLBERT):
            logger.info("Streaming forced no-match response for non-repository intent")
            full_response = _NO_MATCH_CODE_LOOKUP_RESPONSE
            for evt in _build_no_match_events(
                t_start=t_start,
                retrieved_files=retrieved_files,
                t_retrieval_ms=t_retrieval_ms,
                query_mode_value=query_mode_value,
            ):
                yield evt
            return


        # ── Stream LLM response ────────────────────────────────────────────
        t_llm_start = time.time()

        def _fallback_prompt_from_user_question(prompt_text: str) -> str:
            import re

            orig_match = re.search(r"The user specifically asked: '([^']+)'", prompt_text)
            original_question = orig_match.group(1) if orig_match else "the requested review"
            return (
                f"The user asked: '{original_question}'. "
                "Please conduct a general best-practices code review of the repository. "
                "Focus on safe programming structures, input verification, modular design, "
                "and general code architecture. First explicitly name the most relevant file(s) "
                "with your reasons, then list standard architectural recommendations."
            )

        try:
            from app.services.llm_fallback import get_last_llm_usage, reset_last_llm_usage
            reset_last_llm_usage()

            buffer = ""
            is_refusal = False
            refusal_indicators = [
                "i cannot", "i'm sorry", "i am sorry", "as an ai",
                "i am not able", "i cannot fulfill", "unable to comply",
                "cannot fulfill this request"
            ]

            async for delta in _stream_llm_response_with_guard(full_prompt):
                if not is_refusal:
                    buffer += delta
                    lower_buf = buffer.strip().lower()
                    if any(ind in lower_buf for ind in refusal_indicators):
                        is_refusal = True
                        break

                    if len(buffer) >= 60 or "\n" in delta or "." in delta:
                        full_response += buffer
                        yield to_sse_data({'type': 'token', 'content': buffer})
                        buffer = ""
                else:
                    full_response += delta
                    yield to_sse_data({'type': 'token', 'content': delta})

            if is_refusal:
                logger.warning("Streaming refusal detected; retrying with fallback prompt")
                fallback_prompt = _fallback_prompt_from_user_question(full_prompt)
                full_response = ""
                async for delta in _stream_llm_response_with_guard(fallback_prompt):
                    full_response += delta
                    yield to_sse_data({'type': 'token', 'content': delta})
            else:
                if buffer:
                    full_response += buffer
                    yield to_sse_data({'type': 'token', 'content': buffer})

            # Guarantee the UI receives at least one token event.
            if not full_response.strip():
                full_response = _first_token_fallback_response()
                response_path = "safe_fallback"
                yield to_sse_data({'type': 'token', 'content': full_response})
            else:
                response_path = "stream"

            usage = get_last_llm_usage()
            llm_provider = usage.get("provider")
            llm_model = usage.get("model")
        except StreamFirstTokenTimeoutError as timeout_err:
            logger.warning(f"LLM stream startup timeout; attempting non-stream recovery: {timeout_err}")
            full_response, response_path = await _recover_from_stream_failure(full_prompt, timeout_err)
            yield to_sse_data({'type': 'token', 'content': full_response})
        except Exception as llm_err:
            logger.warning(f"LLM streaming failed; attempting non-stream recovery: {llm_err}")
            full_response, response_path = await _recover_from_stream_failure(full_prompt, llm_err)
            yield to_sse_data({'type': 'token', 'content': full_response})

        def _log_stream_outcome(path_value: str) -> None:
            if path_value == "stream":
                logger.debug("Streaming token generation completed successfully")
            else:
                logger.debug("Streaming completed with fallback response path=%s", path_value)

        _log_stream_outcome(response_path)

        t_llm_ms = int((time.time() - t_llm_start) * 1000)
        logger.info(
            "chat_response_path=%s repo_id=%s chat_id=%s query_mode=%s",
            response_path,
            repo_id,
            chat_id,
            query_mode_value,
        )

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
        safe_msg = safe_chat_error_message(e, include_rate_limit=True)
        logger.error(f"Streaming chat error: {safe_msg}", exc_info=True)
        yield to_sse_data({'type': 'error', 'message': safe_msg})

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
    is_cta_followup: bool = False,
) -> Tuple[str, str, List[dict], int]:
    """
    Non-streaming version — used when we need to persist to DB
    but don't need to stream to client.

    Returns (response_str, query_mode, retrieved_files, latency_ms)
    """
    _ensure_llamaindex()

    from app.services.qa_service import handle_user_query
    from functools import partial

    chat_engine, memory, last_mode = _get_or_init_session(repo_id, chat_id)

    t_start = time.time()
    response_str, new_engine, new_memory, query_mode = await asyncio.get_event_loop().run_in_executor(
        None,
        partial(handle_user_query, is_cta_followup=is_cta_followup),
        query,
        index_name,
        chat_engine,
        memory,
        last_mode,
    )
    latency_ms = int((time.time() - t_start) * 1000)

    _save_session(repo_id, chat_id, new_engine, new_memory, query_mode)

    return response_str, query_mode.value, [], latency_ms
