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
from app.retrieval.query_router import classify_query, QueryMode
from app.retrieval.reranker import rerank_with_colbert
from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT
from app.ingestion.file_filter import filter_files
from app.llm.llm_client import configure_llamaindex_settings
from app.config import INDEX_DIR, REPOS_DIR, TOP_K_CHUNKS, TOP_K_RERANK
from app.utils.logger import get_logger

logger = get_logger(__name__)


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


def handle_user_query(
    query: str,
    index_name: str,
    chat_engine=None,
    memory: Optional[ChatMemoryBuffer] = None,
    last_mode: Optional[QueryMode] = None,
) -> Tuple[str, object, ChatMemoryBuffer, QueryMode]:
    """
    Main query entrypoint.

    Returns (response, chat_engine, memory, query_mode) so the UI can:
    - Cache the engine for the next turn
    - Display which mode was used (optional, useful for debugging)

    The chat_engine is rebuilt whenever the query mode switches —
    this preserves memory across turns while using the right retriever.
    """
    logger.info(f"Query [{index_name}]: {query}")

    # ── Ensure LlamaIndex settings ─────────────────────────────────────────
    # Force configured providers to avoid any default-provider drift.
    configure_llamaindex_settings()

    # ── Load indexes ───────────────────────────────────────────────────────
    vector_index, bm25_retriever = _get_indexes(index_name)

    # ── Memory ─────────────────────────────────────────────────────────────
    if memory is None:
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

    # ── Query Resolution (Context-Aware Query Rewriting) ───────────────────
    resolved_query = resolve_ambiguous_query(query, memory)
    if resolved_query != query:
        logger.info(f"Resolved context-aware query: '{resolved_query}'")

    # ── Route query ────────────────────────────────────────────────────────
    query_mode = classify_query(resolved_query)
    logger.info(f"Query mode: {query_mode.value}")

    if query_mode == QueryMode.RELATIONSHIP:
        from app.retrieval.query_router import extract_relationship_target
        from app.llm.prompts import RELATIONSHIP_PROMPT
        
        target = extract_relationship_target(resolved_query)
        logger.info(f"Stage -1: RELATIONSHIP query detected. Target symbol: '{target}'")
        refs = []
        if target:
            graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
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
                    if refs:
                        logger.info(f"Stage -1: Relationship graph lookup SUCCEEDED for '{target}'. Found {len(refs)} references.")
                    else:
                        logger.info(f"Stage -1: Relationship graph lookup EMPTY/FAILED for '{target}'.")
                except Exception as ex:
                    logger.warning(f"Failed to load relationship graph: {ex}")
            else:
                logger.warning(f"Relationship graph file not found at {graph_path}")
        else:
            logger.info("Stage -1: Relationship target extraction returned None.")
        
        ref_list_str = "\n".join([f"- {r}" for r in refs]) if refs else "No references found."
        full_prompt = RELATIONSHIP_PROMPT.format(
            target_symbol=target or "unknown",
            references_list=ref_list_str
        )
        
        response = Settings.llm.complete(full_prompt)
        response_str = str(response).strip()
        
        from llama_index.core.base.llms.types import ChatMessage
        memory.put(ChatMessage(role="user", content=query))
        memory.put(ChatMessage(role="assistant", content=response_str))
        
        return response_str, chat_engine, memory, query_mode

    # Rebuild engine if mode changed (or first query)
    if chat_engine is None or query_mode != last_mode:
        if query_mode == QueryMode.CODE_LOOKUP:
            chat_engine = _build_code_lookup_engine(vector_index, bm25_retriever, memory)
        else:
            chat_engine = _build_architectural_engine(vector_index, memory)

    # ── Retrieve + rerank (ColBERT applied here if enabled) ────────────────
    # CondensePlusContextChatEngine handles retrieval internally,
    # but we intercept nodes for ColBERT reranking before the LLM call.
    #
    # ── COLBERT ON ──────────────────────────────────────────────────────
    # To disable ColBERT: set USE_COLBERT=False in config.py
    from app.config import USE_COLBERT

    if USE_COLBERT:
        # Retrieve nodes manually → rerank → inject into engine response
        try:
            condensed_query = resolved_query
            retriever = chat_engine._retriever
            raw_nodes = retriever.retrieve(condensed_query)
            reranked_nodes = rerank_with_colbert(resolved_query, raw_nodes, top_k=TOP_K_RERANK)

            # Build response using reranked context
            from llama_index.core.response_synthesizers import get_response_synthesizer
            from llama_index.core import QueryBundle

            system_prompt = (
                CODE_LOOKUP_PROMPT
                if query_mode == QueryMode.CODE_LOOKUP
                else ARCHITECTURAL_PROMPT
            )
            synthesizer = get_response_synthesizer(llm=Settings.llm)
            context_str = "\n\n".join([
                f"[{n.node.metadata.get('path', 'unknown')}]\n{n.node.get_content()}"
                for n in reranked_nodes
            ])
            full_prompt = f"{system_prompt}\n\nContext:\n{context_str}\n\nQuestion: {resolved_query}\n\nAnswer:"
            response = Settings.llm.complete(full_prompt)
            response_str = str(response).strip()

            # Update memory manually (storing the ORIGINAL user question)
            from llama_index.core.base.llms.types import ChatMessage
            memory.put(ChatMessage(role="user", content=query))
            memory.put(ChatMessage(role="assistant", content=response_str))

            logger.info(f"ColBERT reranked response generated")
            return response_str, chat_engine, memory, query_mode

        except Exception as e:
            logger.warning(f"ColBERT pipeline failed: {e} — falling back to chat engine")
    # ── END COLBERT ON ───────────────────────────────────────────────────

    # Standard path (ColBERT disabled or failed)
    start = time.time()
    response = chat_engine.chat(resolved_query)
    logger.info(f"Response in {time.time() - start:.2f}s")

    return str(response), chat_engine, memory, query_mode