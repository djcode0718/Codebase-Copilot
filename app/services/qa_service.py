"""
qa_service.py
─────────────
Full query pipeline with dual-mode routing:

  classify_query (QueryRouter)
        │
        ├── CODE_LOOKUP mode ──────────────────────────────────────────────
        │     BM25 + Dense hybrid (RRF fusion)
        │     → ColBERT reranking        ← can be disabled via USE_COLBERT
        │     → Strict "answer from code" prompt
        │
        └── ARCHITECTURAL mode ────────────────────────────────────────────
              Dense retrieval only (architectural context doc surfaces naturally)
              → Larger top_k to catch summary nodes
              → ColBERT reranking        ← can be disabled via USE_COLBERT
              → Relaxed "reason about the codebase" prompt

Both modes use CondensePlusContextChatEngine for multi-turn conversation.
The chat engine condenses follow-up questions into standalone queries before
retrieval — much better than naive history concatenation.
"""

import os
import time
from typing import Optional, Tuple

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.retrievers.bm25 import BM25Retriever

from app.indexing.index_builder import load_vector_index, build_bm25_retriever
from app.retrieval.query_router import classify_query, QueryMode, is_general_knowledge_or_preference_query
from app.retrieval.reranker import rerank_with_colbert
from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT
from app.ingestion.file_filter import filter_files
from app.llm.llm_client import configure_llamaindex_settings
from app.config import INDEX_DIR, REPOS_DIR, TOP_K_CHUNKS, TOP_K_RERANK
from app.utils.logger import get_logger

logger = get_logger(__name__)

_NO_MATCH_CODE_LOOKUP_RESPONSE = (
    "I couldn't find that in the retrieved code. "
    "Try rephrasing or asking about a specific file or function."
)

_CLARIFICATION_RESPONSE = "Could you point me to a specific file, folder, or function? I want to search the right part of the repo."
_REFUSAL_INDICATORS = [
    "i cannot", "i'm sorry", "i am sorry", "as an ai",
    "i am not able", "i cannot fulfill", "unable to comply",
    "cannot fulfill this request",
]


_RESOLVE_QUERY_PROMPT = """Given a conversation history between a User and an Assistant, and a new follow-up question from the User, rewrite the follow-up question into a clear, self-contained standalone question.
Resolve any references, pronouns (like "it", "its", "that", "this"), or context-dependent terms to refer explicitly to what was previously discussed.

Rules:
- Do NOT answer the question.
- Do NOT add any introductory or explanatory text (e.g. "Standalone question:").
- Keep the rewritten question natural and specific to the codebase elements discussed.
- If the question is already standalone and does not need any rewriting, output the original question exactly.

CONVERSATION HISTORY:
{history}

Follow-up Question: {query}

Standalone Question:"""


def resolve_ambiguous_query(query: str, memory: ChatMemoryBuffer) -> str:
    """
    Resolves pronouns and implicit references in follow-up queries using chat memory.
    If there is no history, or rewriting fails, the original query is returned.
    """
    if memory is None:
        return query

    try:
        history_msgs = memory.get()
        if not history_msgs:
            return query

        history_str = ""
        # Format the last 6 messages (3 turns)
        for msg in history_msgs[-6:]:
            role = ""
            content = ""
            if isinstance(msg, dict):
                role = msg.get("role", "")
                content = msg.get("content", "")
            elif hasattr(msg, "role"):
                # Handle ChatMessage object or Enum
                r_val = getattr(msg, "role")
                role = getattr(r_val, "value", r_val) if r_val else ""
                content = getattr(msg, "content", "") or ""
            else:
                try:
                    role = getattr(msg, "role", "")
                    role = getattr(role, "value", role)
                    content = getattr(msg, "content", "")
                except Exception:
                    pass

            if role and content:
                history_str += f"{role.upper()}: {content}\n"

        if not history_str.strip():
            return query

        prompt = _RESOLVE_QUERY_PROMPT.format(history=history_str, query=query)
        response = Settings.llm.complete(prompt)
        resolved = str(response).strip()
        
        if resolved:
            # Clean up potential LLM prefixing or quotes
            resolved = resolved.replace("Standalone question:", "").strip()
            resolved = resolved.strip('"`\'')
            return resolved
    except Exception as e:
        logger.warning(f"Failed to resolve ambiguous query: {e}")

    return query

# ── Session-level cache ────────────────────────────────────────────────────
_index_cache = {}


def _get_indexes(index_name: str):
    """
    Load vector index from ChromaDB and rebuild BM25 retriever.
    Results cached for the session to avoid reloading on every query.
    """
    index_name = (index_name or "").strip()
    if not index_name:
        raise ValueError("index_name cannot be empty when loading indexes")

    if index_name in _index_cache:
        return _index_cache[index_name]

    logger.info(f"Loading indexes for '{index_name}'...")

    vector_index = load_vector_index(index_name)

    # BM25 is rebuilt from disk — fast, no embeddings needed
    repo_path = os.path.join(REPOS_DIR, index_name)
    bm25_retriever = None

    if os.path.exists(repo_path):
        from app.parsing.code_parser import load_documents, parse_documents
        valid_files = filter_files(repo_path)
        documents   = load_documents(valid_files, repo_path)
        nodes       = parse_documents(documents)
        bm25_retriever = build_bm25_retriever(nodes, top_k=TOP_K_CHUNKS)
        logger.info(f"BM25 rebuilt over {len(nodes)} nodes")
    else:
        logger.warning(f"Repo path not found at {repo_path} — BM25 unavailable")

    _index_cache[index_name] = (vector_index, bm25_retriever)
    return vector_index, bm25_retriever


def _build_code_lookup_engine(
    vector_index: VectorStoreIndex,
    bm25_retriever,
    memory: ChatMemoryBuffer,
) -> CondensePlusContextChatEngine:
    """
    CODE_LOOKUP mode engine:
    - BM25 + Dense hybrid retrieval (RRF fusion)
    - ColBERT reranking applied after fusion
    - Strict system prompt
    """
    dense_retriever = vector_index.as_retriever(similarity_top_k=TOP_K_CHUNKS)

    if bm25_retriever is not None:
        retriever = QueryFusionRetriever(
            retrievers=[bm25_retriever, dense_retriever],
            similarity_top_k=TOP_K_CHUNKS,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
        )
        logger.info("CODE_LOOKUP: BM25 + Dense hybrid (RRF)")
    else:
        retriever = dense_retriever
        logger.warning("CODE_LOOKUP: Dense-only (BM25 unavailable)")

    return CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        memory=memory,
        llm=Settings.llm,
        system_prompt=CODE_LOOKUP_PROMPT,
        node_postprocessors=[
            SimilarityPostprocessor(similarity_cutoff=0.0)  # keep all, ColBERT handles filtering
        ],
        verbose=False,
    )


def _build_architectural_engine(
    vector_index: VectorStoreIndex,
    memory: ChatMemoryBuffer,
) -> CondensePlusContextChatEngine:
    """
    ARCHITECTURAL mode engine:
    - Dense-only retrieval with larger top_k
      (the codebase context document surfaces naturally via semantic similarity)
    - No BM25 — keyword matching hurts more than helps for broad questions
    - Relaxed system prompt that allows reasoning beyond the code
    """
    # Larger top_k so the codebase context doc + multiple file summaries
    # are likely to be in the retrieved set
    dense_retriever = vector_index.as_retriever(
        similarity_top_k=TOP_K_CHUNKS + 5
    )

    logger.info("ARCHITECTURAL: Dense retrieval with extended top_k")

    return CondensePlusContextChatEngine.from_defaults(
        retriever=dense_retriever,
        memory=memory,
        llm=Settings.llm,
        system_prompt=ARCHITECTURAL_PROMPT,
        verbose=False,
    )


def _remember_turn(memory: ChatMemoryBuffer, user_text: str, assistant_text: str) -> None:
    from llama_index.core.base.llms.types import ChatMessage

    memory.put(ChatMessage(role="user", content=user_text))
    memory.put(ChatMessage(role="assistant", content=assistant_text))


def _build_review_fallback_prompt(question_source: str) -> str:
    import re

    orig_match = re.search(r"The user specifically asked: '([^']+)'", question_source)
    original_question = orig_match.group(1) if orig_match else "the requested review"
    return (
        f"The user asked: '{original_question}'. "
        "Please conduct a general best-practices code review of the repository. "
        "Focus on safe programming structures, input verification, modular design, "
        "and general code architecture. First explicitly name the most relevant file(s) "
        "with your reasons, then list standard architectural recommendations."
    )


def _has_refusal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(ind in lowered for ind in _REFUSAL_INDICATORS)


def _run_pre_routing_checks(
    query: str,
    index_name: str,
    memory: ChatMemoryBuffer,
    chat_engine,
) -> Optional[Tuple[str, object, ChatMemoryBuffer, QueryMode]]:
    from app.retrieval.query_router import detect_excluded_folder, detect_aggregation, check_superlative_intent

    excluded_folder = detect_excluded_folder(query)
    if excluded_folder:
        logger.info("Early exit: excluded folder reference detected")
        err_msg = f"That folder ({excluded_folder}) is excluded from indexing (build/CI/dependency artifacts aren't indexed by default)."
        _remember_turn(memory, query, err_msg)
        return err_msg, chat_engine, memory, QueryMode.CODE_LOOKUP

    if detect_aggregation(query):
        logger.info("Early exit: aggregation query")
        from app.services.repo_stats_service import handle_aggregation_query

        response_str = handle_aggregation_query(query, index_name)
        _remember_turn(memory, query, response_str)
        return response_str, chat_engine, memory, QueryMode.CODE_LOOKUP

    superlative_suggest = check_superlative_intent(query)
    if superlative_suggest:
        logger.info("Early exit: superlative action suggestion")
        import json

        response_str = json.dumps(superlative_suggest)
        _remember_turn(memory, query, response_str)
        return response_str, chat_engine, memory, QueryMode.CODE_LOOKUP

    return None


def _resolve_query_mode(query: str, memory: ChatMemoryBuffer) -> Tuple[str, QueryMode]:
    from app.retrieval.query_router import _is_relationship_query

    if _is_relationship_query(query):
        logger.info("Query mode relationship detected on raw query")
        return query, QueryMode.RELATIONSHIP

    resolved_query = resolve_ambiguous_query(query, memory)
    if resolved_query != query:
        logger.debug("Resolved ambiguous query for retrieval routing")

    if is_general_knowledge_or_preference_query(query) or is_general_knowledge_or_preference_query(resolved_query):
        logger.info("Query classified as out-of-scope; returning no-match response")
        return resolved_query, QueryMode.CODE_LOOKUP

    query_mode = classify_query(resolved_query)
    logger.info("Query mode selected: %s", query_mode.value)
    return resolved_query, query_mode


def _handle_relationship_query(
    query: str,
    resolved_query: str,
    index_name: str,
    memory: ChatMemoryBuffer,
    chat_engine,
    query_mode: QueryMode,
) -> Tuple[str, object, ChatMemoryBuffer, QueryMode]:
    from app.retrieval.query_router import extract_relationship_target
    from app.llm.prompts import RELATIONSHIP_PROMPT

    target = extract_relationship_target(resolved_query)
    logger.info("Relationship query target extracted: %s", target)
    refs = []
    if target:
        graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
        logger.debug("Relationship graph lookup path: %s", graph_path)
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
                logger.info("Relationship lookup completed with %s references", len(refs))
            except Exception as ex:
                logger.warning(f"Failed to load relationship graph: {ex}")
        else:
            logger.warning(f"Relationship graph file not found at {graph_path}")
    else:
        logger.info("Relationship target extraction returned None")

    ref_list_str = "\n".join([f"- {r}" for r in refs]) if refs else "No references found."
    full_prompt = RELATIONSHIP_PROMPT.format(
        target_symbol=target or "unknown",
        references_list=ref_list_str,
    )

    response = Settings.llm.complete(full_prompt)
    response_str = str(response).strip()
    _remember_turn(memory, query, response_str)
    return response_str, chat_engine, memory, query_mode


def _ensure_engine_for_mode(chat_engine, query_mode: QueryMode, last_mode: Optional[QueryMode], vector_index, bm25_retriever, memory):
    if chat_engine is None or query_mode != last_mode:
        logger.debug("Rebuilding chat engine for mode=%s (last_mode=%s)", query_mode.value, getattr(last_mode, "value", None))
        if query_mode == QueryMode.CODE_LOOKUP:
            return _build_code_lookup_engine(vector_index, bm25_retriever, memory)
        return _build_architectural_engine(vector_index, memory)
    return chat_engine


def _check_low_confidence(nodes, label: str) -> bool:
    from app.retrieval.query_router import LOW_CONFIDENCE_SIMILARITY_THRESHOLD

    top_score = max((float(n.score or 0.0) for n in nodes), default=0.0)
    logger.debug("%s confidence score evaluated: top_score=%.3f threshold=%.3f", label, top_score, LOW_CONFIDENCE_SIMILARITY_THRESHOLD)
    if top_score < LOW_CONFIDENCE_SIMILARITY_THRESHOLD:
        logger.info("Low confidence (%s): top_score %.3f < %.3f", label, top_score, LOW_CONFIDENCE_SIMILARITY_THRESHOLD)
        return True
    return False


def _execute_colbert_path(query: str, resolved_query: str, query_mode: QueryMode, chat_engine, memory):
    retriever = chat_engine._retriever
    raw_nodes = retriever.retrieve(resolved_query)
    logger.debug("ColBERT path retrieved %s raw nodes", len(raw_nodes))
    reranked_nodes = rerank_with_colbert(resolved_query, raw_nodes, top_k=TOP_K_RERANK)
    logger.debug("ColBERT reranked to %s nodes", len(reranked_nodes))

    if _check_low_confidence(reranked_nodes, "ColBERT"):
        _remember_turn(memory, query, _CLARIFICATION_RESPONSE)
        return _CLARIFICATION_RESPONSE

    system_prompt = CODE_LOOKUP_PROMPT if query_mode == QueryMode.CODE_LOOKUP else ARCHITECTURAL_PROMPT
    context_str = "\n\n".join([
        f"[{n.node.metadata.get('path', 'unknown')}]\n{n.node.get_content()}"
        for n in reranked_nodes
    ])
    full_prompt = f"{system_prompt}\n\nContext:\n{context_str}\n\nQuestion: {resolved_query}\n\nAnswer:"
    response = Settings.llm.complete(full_prompt)
    response_str = str(response).strip()

    if _has_refusal(response_str):
        logger.warning("Safety refusal detected in ColBERT path; using fallback prompt")
        response = Settings.llm.complete(_build_review_fallback_prompt(full_prompt))
        response_str = str(response).strip()

    _remember_turn(memory, query, response_str)
    return response_str


def _execute_standard_path(query: str, resolved_query: str, query_mode: QueryMode, chat_engine, memory):
    try:
        retriever = chat_engine._retriever
        raw_nodes = retriever.retrieve(resolved_query)
        logger.debug("Standard path retrieved %s raw nodes", len(raw_nodes))
        if _check_low_confidence(raw_nodes, "RAG"):
            _remember_turn(memory, query, _CLARIFICATION_RESPONSE)
            return _CLARIFICATION_RESPONSE
    except Exception as e:
        logger.warning(f"Failed to check low confidence threshold: {e}")

    start = time.time()
    response = chat_engine.chat(resolved_query)
    response_str = str(response).strip()
    logger.debug("Standard chat engine call completed in %.2fs", time.time() - start)
    if _has_refusal(response_str):
        logger.warning("Safety refusal detected in standard path; using fallback prompt")
        response = Settings.llm.complete(_build_review_fallback_prompt(resolved_query))
        response_str = str(response).strip()
        _remember_turn(memory, query, response_str)
    return response_str


def handle_user_query(
    query: str,
    index_name: str,
    chat_engine=None,
    memory: Optional[ChatMemoryBuffer] = None,
    last_mode: Optional[QueryMode] = None,
    is_cta_followup: bool = False,
) -> Tuple[str, object, ChatMemoryBuffer, QueryMode]:
    """
    Main query entrypoint.

    Returns (response, chat_engine, memory, query_mode) so the UI can:
    - Cache the engine for the next turn
    - Display which mode was used (optional, useful for debugging)

    The chat_engine is rebuilt whenever the query mode switches —
    this preserves memory across turns while using the right retriever.
    """
    logger.info("Query received for index=%s (length=%s)", index_name, len(query or ""))

    configure_llamaindex_settings()
    logger.debug("LlamaIndex settings configured")

    vector_index, bm25_retriever = _get_indexes(index_name)
    logger.debug("Indexes loaded for index=%s (bm25_available=%s)", index_name, bm25_retriever is not None)

    if memory is None:
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        logger.debug("Initialized new chat memory buffer")

    if not is_cta_followup:
        precheck_result = _run_pre_routing_checks(query, index_name, memory, chat_engine)
        if precheck_result is not None:
            return precheck_result

    resolved_query, query_mode = _resolve_query_mode(query, memory)
    if query_mode == QueryMode.CODE_LOOKUP and (
        is_general_knowledge_or_preference_query(query)
        or is_general_knowledge_or_preference_query(resolved_query)
    ):
        _remember_turn(memory, query, _NO_MATCH_CODE_LOOKUP_RESPONSE)
        return _NO_MATCH_CODE_LOOKUP_RESPONSE, chat_engine, memory, QueryMode.CODE_LOOKUP

    if query_mode == QueryMode.RELATIONSHIP:
        return _handle_relationship_query(query, resolved_query, index_name, memory, chat_engine, query_mode)

    chat_engine = _ensure_engine_for_mode(
        chat_engine,
        query_mode,
        last_mode,
        vector_index,
        bm25_retriever,
        memory,
    )

    from app.config import USE_COLBERT

    if USE_COLBERT:
        try:
            logger.debug("Executing ColBERT path for query_mode=%s", query_mode.value)
            response_str = _execute_colbert_path(query, resolved_query, query_mode, chat_engine, memory)
            return response_str, chat_engine, memory, query_mode
        except Exception as e:
            logger.warning(f"ColBERT pipeline failed: {e} — falling back to chat engine")

    logger.debug("Executing standard chat-engine path for query_mode=%s", query_mode.value)
    response_str = _execute_standard_path(query, resolved_query, query_mode, chat_engine, memory)
    return response_str, chat_engine, memory, query_mode
