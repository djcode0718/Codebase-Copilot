"""
qa_service.py
─────────────
Full query pipeline with dual-mode routing:

  classify_query (QueryRouter)
        │
        ├── CODE_LOOKUP mode ──────────────────────────────────────────────
        │     BM25 + Dense hybrid (RRF fusion)
        │     → Reranking                ← can be disabled via USE_RERANKER
        │     → Strict "answer from code" prompt
        │
        └── ARCHITECTURAL mode ────────────────────────────────────────────
              Dense retrieval only (architectural context doc surfaces naturally)
              → Larger top_k to catch summary nodes
              → Reranking                ← can be disabled via USE_RERANKER
              → Relaxed "reason about the codebase" prompt

Both modes use CondensePlusContextChatEngine for multi-turn conversation.
The chat engine condenses follow-up questions into standalone queries before
retrieval — much better than naive history concatenation.
"""

import os
import time
import re
from typing import Optional, Tuple, Set, List

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.retrievers.bm25 import BM25Retriever

from app.indexing.index_builder import load_vector_index, build_bm25_retriever
from app.retrieval.query_router import classify_query, QueryMode, is_general_knowledge_or_preference_query
from app.retrieval.reranker import rerank_with_cross_encoder
from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT
from app.ingestion.file_filter import filter_files
from app.llm.llm_client import configure_llamaindex_settings
from app.config import INDEX_DIR, REPOS_DIR, TOP_K_CHUNKS, TOP_K_RERANK
from app.utils.logger import get_logger

logger = get_logger(__name__)

def _get_file_line_count(file_path: str) -> Optional[int]:
    """Return total number of lines in file if it exists, else None."""
    try:
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
    except Exception:
        pass
    return None


_CITATION_REGEX = re.compile(
    r'(?P<prefix>\[`?|`|\b)'
    r'(?P<path>[a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]{2,4})'
    r'(?:(?::|#L?)(?P<start>\d+)(?:-(?:L)?(?P<end>\d+))?)?'
    r'(?P<suffix>`?\]?|`|\b)'
)

_VALID_EXTENSIONS = {
    "py", "js", "ts", "jsx", "tsx", "html", "css", "json", "yml", "yaml",
    "md", "sh", "go", "rs", "cpp", "c", "h", "java", "sql", "txt"
}


def extract_cited_files(text: str) -> Set[str]:
    matches = re.findall(r"\b[a-zA-Z0-9_\-\./]+\.[a-zA-Z0-9]{2,4}\b", text)
    results = set()
    for m in matches:
        m_clean = m.strip("`'\".,()[]{}")
        if m_clean.endswith((".", "/")):
            continue
        ext = m_clean.split(".")[-1].lower()
        if ext in _VALID_EXTENSIONS:
            results.add(m_clean)
    return results


def extract_citations_with_lines(text: str) -> List[dict]:
    citations = []
    seen = set()
    for match in _CITATION_REGEX.finditer(text):
        raw = match.group(0)
        path = match.group("path").strip("`'\".,()[]{}")
        if path.endswith((".", "/")):
            continue
        ext = path.split(".")[-1].lower()
        if ext not in _VALID_EXTENSIONS:
            continue
        start_line = int(match.group("start")) if match.group("start") else None
        end_line = int(match.group("end")) if match.group("end") else None
        key = (path, start_line, end_line)
        if key not in seen:
            seen.add(key)
            citations.append({
                "raw": raw,
                "path": path,
                "start_line": start_line,
                "end_line": end_line,
            })
    return citations


def validate_citation_details(
    text: str,
    retrieved_paths: Set[str],
    repo_path: str,
) -> dict:
    citations = extract_citations_with_lines(text)
    details = {
        "valid": [],
        "invalid_files": [],
        "fabricated_lines": [],
        "outside_context": [],
    }

    norm_retrieved = {os.path.normpath(p) for p in (retrieved_paths or set()) if p}

    for cite in citations:
        path = cite["path"]
        start_line = cite["start_line"]
        end_line = cite["end_line"]
        full_path = os.path.join(repo_path, path) if repo_path else ""

        is_in_retrieved = (
            path in retrieved_paths
            or os.path.normpath(path) in norm_retrieved
            or any(r.endswith(path) or path.endswith(r) for r in retrieved_paths)
        )
        file_exists = bool(full_path and os.path.exists(full_path))

        if not file_exists and not is_in_retrieved:
            if path not in details["invalid_files"]:
                details["invalid_files"].append(path)
            continue

        # Check line numbers if file exists on disk
        if file_exists and start_line is not None:
            line_count = _get_file_line_count(full_path)
            if line_count is not None and (start_line > line_count or start_line <= 0):
                details["fabricated_lines"].append({
                    "path": path,
                    "line": start_line,
                    "max_lines": line_count,
                })
                continue

        # Citation is valid; check whether in context or outside context
        if not is_in_retrieved and file_exists:
            details["outside_context"].append(path)

        details["valid"].append({
            "path": path,
            "start_line": start_line,
            "end_line": end_line,
            "in_context": is_in_retrieved,
        })

    return details


def validate_citations(
    text: str,
    retrieved_paths: Set[str],
    repo_path: str
) -> List[str]:
    details = validate_citation_details(text, retrieved_paths, repo_path)
    invalid = list(details["invalid_files"])
    for fab in details["fabricated_lines"]:
        invalid.append(f"{fab['path']}:{fab['line']}")
    return sorted(list(set(invalid)))


def sanitize_citations(text: str, retrieved_paths: Set[str], repo_path: str) -> str:
    """
    Sanitize response text by:
    1. Stripping fabricated line numbers from valid files (leaving valid file reference intact).
    2. Removing or unlinking invalid/hallucinated filenames so they are not delivered as verified citations.
    3. Preserving all valid citations and their valid line references.
    """
    if not text:
        return text

    details = validate_citation_details(text, retrieved_paths, repo_path)
    invalid_files = set(details["invalid_files"])
    fabricated_lines = {item["path"]: item["line"] for item in details["fabricated_lines"]}

    if not invalid_files and not fabricated_lines:
        return text

    sanitized = text

    # Strip fabricated line numbers from references to valid files (e.g. `valid.py:9999` -> `valid.py`)
    for path, bad_line in fabricated_lines.items():
        pattern = re.compile(re.escape(path) + r'(?::|#L?)' + str(bad_line) + r'(?:-(?:L)?\d+)?\b')
        sanitized = pattern.sub(path, sanitized)

    # For invalid/hallucinated files, remove or neutralize them
    for bad_file in invalid_files:
        md_link_pattern = re.compile(r'\[([^\]]+)\]\(' + re.escape(bad_file) + r'(?:#[^)]*)?\)')
        sanitized = md_link_pattern.sub(r'\1', sanitized)
        bracket_pattern = re.compile(r'\[`?' + re.escape(bad_file) + r'(?::\d+(?:-\d+)?)?`?\]')
        sanitized = bracket_pattern.sub("[unverified reference omitted]", sanitized)
        backtick_pattern = re.compile(r'`' + re.escape(bad_file) + r'(?::\d+(?:-\d+)?)?`')
        sanitized = backtick_pattern.sub("[unverified reference omitted]", sanitized)
        word_pattern = re.compile(r'\b' + re.escape(bad_file) + r'(?::\d+(?:-\d+)?)?\b')
        sanitized = word_pattern.sub("[unverified reference omitted]", sanitized)

    return sanitized


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


def invalidate_index_cache(index_name: Optional[str] = None) -> None:
    """Invalidate in-memory index cache for a specific index or all indexes."""
    global _index_cache
    if index_name:
        _index_cache.pop(index_name, None)
        logger.info("Invalidated in-memory index cache for '%s'", index_name)
    else:
        _index_cache.clear()
        logger.info("Invalidated all in-memory index caches")


def _get_indexes(index_name: str, wait_timeout: float = 5.0):
    """
    Load vector index from ChromaDB and rebuild BM25 retriever.
    Results cached for the session to avoid reloading on every query.
    Enforces read safety during active incremental refresh to prevent
    queries from observing partially mutated Chroma vectors.
    """
    index_name = (index_name or "").strip()
    if not index_name:
        raise ValueError("index_name cannot be empty when loading indexes")

    from app.indexing.incremental import acquire_index_read
    with acquire_index_read(index_name, timeout=wait_timeout):
        if index_name in _index_cache:
            return _index_cache[index_name]

        logger.info(f"Loading indexes for '{index_name}'...")

        vector_index = load_vector_index(index_name)

        # BM25 is rebuilt from disk — fast, no embeddings needed
        repo_path = os.path.join(REPOS_DIR, index_name)
        bm25_retriever = None

        if os.path.exists(repo_path):
            from app.parsing.code_parser import load_documents, parse_documents
            from app.ingestion.git_history import load_persisted_git_history
            valid_files = filter_files(repo_path)
            documents   = load_documents(valid_files, repo_path)
            nodes       = parse_documents(documents)
            
            git_docs = load_persisted_git_history(index_name)
            nodes = nodes + git_docs
            
            bm25_retriever = build_bm25_retriever(nodes, top_k=TOP_K_CHUNKS)
            logger.info(f"BM25 rebuilt over {len(nodes)} nodes (including {len(git_docs)} git history nodes)")
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
    - Cross-Encoder reranking applied after fusion
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
            SimilarityPostprocessor(similarity_cutoff=0.0)  # keep all, Cross-Encoder handles filtering
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
    from app.retrieval.query_router import detect_excluded_folder, detect_aggregation, check_superlative_intent, detect_greeting, GREETING_RESPONSE

    if detect_greeting(query):
        logger.info("Early exit: greeting detected")
        _remember_turn(memory, query, GREETING_RESPONSE)
        return GREETING_RESPONSE, chat_engine, memory, QueryMode.CODE_LOOKUP

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

    superlative_suggest = check_superlative_intent(query, index_name=index_name)
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


def _get_relationship_refs(index_name: str, target: Optional[str]) -> List[str]:
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
    return refs


def _handle_relationship_query(
    query: str,
    resolved_query: str,
    index_name: str,
    memory: ChatMemoryBuffer,
    chat_engine,
    query_mode: QueryMode,
    target: Optional[str] = None,
    refs: Optional[List[str]] = None,
) -> Tuple[str, object, ChatMemoryBuffer, QueryMode]:
    from app.retrieval.query_router import extract_relationship_target, is_real_identifier
    from app.llm.prompts import RELATIONSHIP_PROMPT

    if target is None:
        target = extract_relationship_target(resolved_query)
        logger.info("Relationship query target extracted: %s", target)
        if not is_real_identifier(target, index_name):
            logger.info(f"Stage -1: RELATIONSHIP target '{target}' is not a real identifier. Forcing clarification.")
            _remember_turn(memory, query, _CLARIFICATION_RESPONSE)
            return _CLARIFICATION_RESPONSE, chat_engine, memory, query_mode

    if refs is None:
        from app.indexing.incremental import acquire_index_read
        with acquire_index_read(index_name):
            refs = _get_relationship_refs(index_name, target)

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


def _check_low_confidence(nodes, label: str, query_mode: Optional[QueryMode] = None) -> bool:
    """
    Check if retrieved nodes have sufficiently low confidence to warrant clarification.
    Safely differentiates score types:
    - Empty nodes: always low confidence (genuine no-results).
    - RRF scores (max ~0.05): scale mismatch - never reject RRF nodes based on a 0.40 threshold.
    - ARCHITECTURAL mode: broad questions reasoning over code context should not be aborted.
    - CrossEncoder scores: only reject when scores are genuinely negligible (< 0.20) indicating no evidence.
    """
    if not nodes:
        logger.info("Low confidence (%s): no nodes retrieved", label)
        return True

    if query_mode == QueryMode.ARCHITECTURAL:
        return False

    from app.retrieval.query_router import LOW_CONFIDENCE_SIMILARITY_THRESHOLD
    top_score = max((float(n.score or 0.0) for n in nodes), default=0.0)
    logger.debug("%s confidence score evaluated: top_score=%.3f threshold=%.3f", label, top_score, LOW_CONFIDENCE_SIMILARITY_THRESHOLD)

    # RRF scores from QueryFusionRetriever are in [0, ~0.10].
    # Comparing RRF scores against a 0.40 threshold is an incompatible scale error.
    if top_score <= 0.10 and any(n.score is not None for n in nodes):
        logger.debug("%s: Detected RRF score scale (top_score=%.4f); preserving retrieved nodes for generation.", label, top_score)
        return False

    # For normalized cross-encoder / vector similarity scores:
    # A true low confidence threshold is when top_score is genuinely low (< 0.20).
    effective_threshold = min(LOW_CONFIDENCE_SIMILARITY_THRESHOLD, 0.20)
    if top_score < effective_threshold:
        logger.info("Low confidence (%s): top_score %.3f < %.3f", label, top_score, effective_threshold)
        return True

    return False


def _execute_cross_encoder_path(
    query: str,
    resolved_query: str,
    query_mode: QueryMode,
    chat_engine,
    memory: ChatMemoryBuffer,
    index_name: str,
    reranked_nodes: Optional[List] = None,
) -> str:
    from app.config import get_repos_dir, CITATION_VALIDATION_MODE
    repo_path = os.path.join(get_repos_dir(), index_name)

    if reranked_nodes is None:
        retriever = chat_engine._retriever
        raw_nodes = retriever.retrieve(resolved_query)
        logger.debug("Cross-Encoder path retrieved %s raw nodes", len(raw_nodes))
        reranked_nodes = rerank_with_cross_encoder(resolved_query, raw_nodes, top_k=TOP_K_RERANK, index_name=index_name)
        logger.debug("Cross-Encoder reranked to %s nodes", len(reranked_nodes))

    if _check_low_confidence(reranked_nodes, "Cross-Encoder", query_mode=query_mode):
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
        logger.warning("Safety refusal detected in Cross-Encoder path; using fallback prompt")
        response = Settings.llm.complete(_build_review_fallback_prompt(full_prompt))
        response_str = str(response).strip()

    # Citation validation check
    retrieved_paths = {n.node.metadata.get("path") for n in reranked_nodes if n.node.metadata.get("path")}
    invalid_citations = validate_citations(response_str, retrieved_paths, repo_path)
    if invalid_citations:
        if CITATION_VALIDATION_MODE == "strict":
            for attempt in range(2):
                logger.warning(f"Hallucination detected (attempt {attempt+1}): {invalid_citations}. Retrying...")
                valid_paths_str = ", ".join(sorted(retrieved_paths))
                hallucinated_str = ", ".join(invalid_citations)
                retry_prompt = (
                    f"{full_prompt}\n\n"
                    f"The previous response hallucinated non-existent files: {hallucinated_str}. "
                    f"Please generate a response using ONLY valid file paths from the retrieved context: {valid_paths_str}.\n\n"
                    f"Answer:"
                )
                response = Settings.llm.complete(retry_prompt)
                response_str = str(response).strip()
                invalid_citations = validate_citations(response_str, retrieved_paths, repo_path)
                if not invalid_citations:
                    logger.info("Hallucination resolved after retry.")
                    break
            if invalid_citations:
                logger.warning(f"Strict citation validation: sanitizing {len(invalid_citations)} unverified reference(s) from response")
                response_str = sanitize_citations(response_str, retrieved_paths, repo_path)
        elif CITATION_VALIDATION_MODE == "filter":
            response_str = sanitize_citations(response_str, retrieved_paths, repo_path)
        else:
            logger.warning(f"Response cited hallucinated files: {invalid_citations}")

    _remember_turn(memory, query, response_str)
    return response_str


def _execute_standard_path(
    query: str,
    resolved_query: str,
    query_mode: QueryMode,
    chat_engine,
    memory: ChatMemoryBuffer,
    index_name: str,
    raw_nodes: Optional[List] = None,
) -> str:
    from app.config import get_repos_dir, CITATION_VALIDATION_MODE
    repo_path = os.path.join(get_repos_dir(), index_name)

    if raw_nodes is None:
        try:
            retriever = chat_engine._retriever
            raw_nodes = retriever.retrieve(resolved_query)
            logger.debug("Standard path retrieved %s raw nodes", len(raw_nodes))
            if _check_low_confidence(raw_nodes, "RAG", query_mode=query_mode):
                _remember_turn(memory, query, _CLARIFICATION_RESPONSE)
                return _CLARIFICATION_RESPONSE
        except Exception as e:
            logger.warning(f"Failed to check low confidence threshold: {e}")
    else:
        if _check_low_confidence(raw_nodes, "RAG", query_mode=query_mode):
            _remember_turn(memory, query, _CLARIFICATION_RESPONSE)
            return _CLARIFICATION_RESPONSE

    start = time.time()
    if hasattr(chat_engine, "_get_response_synthesizer") and raw_nodes is not None:
        try:
            chat_history = memory.get(input=resolved_query) if memory else []
            synthesizer = chat_engine._get_response_synthesizer(chat_history)
            response = synthesizer.synthesize(resolved_query, raw_nodes)
            response_str = str(response).strip()
            if hasattr(chat_engine, "_memory") and chat_engine._memory is not None:
                from llama_index.core.llms import ChatMessage, MessageRole
                chat_engine._memory.put(ChatMessage(content=resolved_query, role=MessageRole.USER))
                chat_engine._memory.put(ChatMessage(content=response_str, role=MessageRole.ASSISTANT))
        except Exception as ex:
            logger.warning(f"Direct synthesis failed; falling back to chat_engine.chat: {ex}")
            response = chat_engine.chat(resolved_query)
            response_str = str(response).strip()
    else:
        response = chat_engine.chat(resolved_query)
        response_str = str(response).strip()

    logger.debug("Standard chat engine call completed in %.2fs", time.time() - start)
    if _has_refusal(response_str):
        logger.warning("Safety refusal detected in standard path; using fallback prompt")
        response = Settings.llm.complete(_build_review_fallback_prompt(resolved_query))
        response_str = str(response).strip()

    # Standard path citation check
    retrieved_paths = {n.node.metadata.get("path") for n in (raw_nodes or []) if n.node.metadata.get("path")}
    invalid_citations = validate_citations(response_str, retrieved_paths, repo_path)
    if invalid_citations:
        if CITATION_VALIDATION_MODE == "strict":
            for attempt in range(2):
                logger.warning(f"Hallucination detected in standard path (attempt {attempt+1}): {invalid_citations}. Retrying...")
                valid_paths_str = ", ".join(sorted(retrieved_paths))
                hallucinated_str = ", ".join(invalid_citations)
                retry_prompt = (
                    f"The previous response hallucinated non-existent files: {hallucinated_str}. "
                    f"Please generate a response using ONLY valid file paths from the retrieved context: {valid_paths_str}."
                )
                response = chat_engine.chat(retry_prompt)
                response_str = str(response).strip()
                invalid_citations = validate_citations(response_str, retrieved_paths, repo_path)
                if not invalid_citations:
                    logger.info("Hallucination resolved after retry.")
                    break
            if invalid_citations:
                logger.warning(f"Strict citation validation: sanitizing {len(invalid_citations)} unverified reference(s) from standard response")
                response_str = sanitize_citations(response_str, retrieved_paths, repo_path)
        elif CITATION_VALIDATION_MODE == "filter":
            response_str = sanitize_citations(response_str, retrieved_paths, repo_path)
        else:
            logger.warning(f"Standard path response cited hallucinated files: {invalid_citations}")

    _remember_turn(memory, query, response_str)
    return response_str


def handle_user_query(
    query: str,
    index_name: str,
    chat_engine=None,
    memory: Optional[ChatMemoryBuffer] = None,
    last_mode: Optional[QueryMode] = None,
    is_cta_followup: bool = False,
    target_repo_id: Optional[str] = None,
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

    if memory is None:
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
        logger.debug("Initialized new chat memory buffer")

    from app.indexing.incremental import acquire_index_read, IndexRefreshingError
    try:
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
            from app.retrieval.query_router import extract_relationship_target, is_real_identifier
            target = extract_relationship_target(resolved_query)
            logger.info("Relationship query target extracted: %s", target)
            if not is_real_identifier(target, index_name):
                logger.info(f"Stage -1: RELATIONSHIP target '{target}' is not a real identifier. Forcing clarification.")
                _remember_turn(memory, query, _CLARIFICATION_RESPONSE)
                return _CLARIFICATION_RESPONSE, chat_engine, memory, query_mode
            with acquire_index_read(index_name):
                refs = _get_relationship_refs(index_name, target)
            return _handle_relationship_query(
                query, resolved_query, index_name, memory, chat_engine, query_mode, target=target, refs=refs
            )

        retrieved_nodes = None
        should_abstain = False
        abstention_message = None

        with acquire_index_read(index_name):
            vector_index, bm25_retriever = _get_indexes(index_name)
            logger.debug("Indexes loaded for index=%s (bm25_available=%s)", index_name, bm25_retriever is not None)

            chat_engine = _ensure_engine_for_mode(
                chat_engine,
                query_mode,
                last_mode,
                vector_index,
                bm25_retriever,
                memory,
            )

            from app.retrieval.orchestrator import get_retrieval_orchestrator, RetrievalTier
            retriever_source = getattr(chat_engine, "_retriever", None) or vector_index
            decision = get_retrieval_orchestrator().orchestrate(
                query=query,
                index_name=index_name,
                vector_index=retriever_source,
                bm25_retriever=bm25_retriever,
                memory=memory,
                last_mode=last_mode,
                is_cta_followup=is_cta_followup,
                query_mode=query_mode,
                resolved_query=resolved_query,
                rerank_fn=rerank_with_cross_encoder,
                target_repo_id=target_repo_id,
            )
            retrieved_nodes = decision.nodes
            should_abstain = decision.should_abstain
            abstention_message = decision.abstention_message

        # Read lock is released! LLM network inference and synthesis run outside read lock:
        if should_abstain:
            abstention_resp = abstention_message or _CLARIFICATION_RESPONSE
            _remember_turn(memory, query, abstention_resp)
            return abstention_resp, chat_engine, memory, query_mode
        from app.config import USE_RERANKER
        if USE_RERANKER:
            try:
                logger.debug("Executing Reranker path for query_mode=%s", query_mode.value)
                response_str = _execute_cross_encoder_path(
                    query, resolved_query, query_mode, chat_engine, memory, index_name, reranked_nodes=retrieved_nodes
                )
                return response_str, chat_engine, memory, query_mode
            except Exception as e:
                logger.warning(f"Reranker pipeline failed: {e} — falling back to chat engine")

        logger.debug("Executing standard chat-engine path for query_mode=%s", query_mode.value)
        response_str = _execute_standard_path(
            query, resolved_query, query_mode, chat_engine, memory, index_name, raw_nodes=retrieved_nodes
        )
        return response_str, chat_engine, memory, query_mode

    except IndexRefreshingError as e:
        logger.warning("Query rejected during active refresh: %s", e)
        retry_msg = "The repository index is currently being updated. Please retry in a moment."
        _remember_turn(memory, query, retry_msg)
        return retry_msg, chat_engine, memory, QueryMode.CODE_LOOKUP
