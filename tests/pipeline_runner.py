#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          CODEBASE COPILOT — FULL PIPELINE TEST RUNNER                      ║
║                                                                              ║
║  Runs the complete pipeline end-to-end WITHOUT Supabase or the API layer:   ║
║    1. Clone repo                                                             ║
║    2. Filter code files                                                      ║
║    3. Parse + chunk documents                                                ║
║    4. Build embeddings (Ollama / Groq)                                       ║
║    5. Build BM25 keyword index                                               ║
║    6. Interactive chat REPL with dual-mode routing + Cross-Encoder reranking ║
║                                                                              ║
║  Usage:                                                                      ║
║    conda run -n ai-copilot-env python3 tests/pipeline_runner.py              ║
║                                                                              ║
║  Hardcoded repo: https://github.com/djcode0718/InstagramCarouselSplitter     ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import shutil
import textwrap
from datetime import datetime

# ── Make project root importable ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Silence LlamaIndex / httpx noise until we want it
import logging
logging.getLogger("llama_index").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)

# ── Styling ───────────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RED    = "\033[91m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
WHITE  = "\033[97m"

REPO_URL   = "https://github.com/djcode0718/InstagramCarouselSplitter"
INDEX_NAME = "InstagramCarouselSplitter"

_step_timings = {}   # step_name → elapsed_seconds


def banner():
    print(f"\n{BOLD}{CYAN}{'═'*78}{RESET}")
    print(f"{BOLD}{CYAN}  CODEBASE COPILOT — FULL PIPELINE TEST{RESET}")
    print(f"{CYAN}{'═'*78}{RESET}")
    print(f"  {DIM}Repo : {REPO_URL}{RESET}")
    print(f"  {DIM}Time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print(f"{CYAN}{'═'*78}{RESET}\n")


def section(title: str):
    print(f"\n{BOLD}{BLUE}┌─  {title}  {'─'*(70-len(title))}┐{RESET}")


def step_start(name: str, detail: str = ""):
    detail_str = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"  {YELLOW}▶{RESET}  {BOLD}{name}{RESET}{detail_str}", flush=True)
    _step_timings[name] = time.time()


def step_done(name: str, detail: str = ""):
    elapsed = time.time() - _step_timings.get(name, time.time())
    detail_str = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"  {GREEN}✓{RESET}  {BOLD}{name}{RESET}  {DIM}({elapsed:.2f}s){RESET}{detail_str}", flush=True)
    return elapsed


def step_fail(name: str, err: str):
    print(f"  {RED}✗{RESET}  {BOLD}{name}{RESET}  {RED}{err}{RESET}", flush=True)


def info(msg: str):
    print(f"     {DIM}│  {msg}{RESET}", flush=True)


def metric(label: str, value):
    print(f"     {CYAN}│  {label:<28}{RESET}{BOLD}{WHITE}{value}{RESET}", flush=True)


def divider():
    print(f"  {DIM}{'─'*70}{RESET}", flush=True)


def chat_header():
    print(f"\n{BOLD}{MAGENTA}{'═'*78}{RESET}")
    print(f"{BOLD}{MAGENTA}  INTERACTIVE CHAT REPL{RESET}")
    print(f"{MAGENTA}  Type your question and press Enter.  Commands: :quit  :mode  :files{RESET}")
    print(f"{BOLD}{MAGENTA}{'═'*78}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# PRE-FLIGHT CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def preflight_check():
    section("PRE-FLIGHT CHECKS")

    # Check Ollama
    step_start("Ollama connectivity", "http://localhost:11434")
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code != 200:
            step_fail("Ollama connectivity", f"HTTP {r.status_code}")
            sys.exit(1)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        step_done("Ollama connectivity", f"{len(models)} models loaded")
    except Exception as e:
        step_fail("Ollama connectivity", f"Not reachable — {e}")
        print(f"\n  {RED}→ Start Ollama with: ollama serve{RESET}\n")
        sys.exit(1)

    # Check nomic-embed-text
    step_start("Embedding model", "nomic-embed-text")
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        models = [m.get("name", "") for m in r.json().get("models", [])]
        if any(m.startswith("nomic-embed-text") for m in models):
            step_done("Embedding model", "nomic-embed-text ✓")
        else:
            step_fail("Embedding model", "not found")
            print(f"\n  {RED}→ Run: ollama pull nomic-embed-text{RESET}\n")
            sys.exit(1)
    except Exception as e:
        step_fail("Embedding model", str(e))
        sys.exit(1)

    # Check .env + config
    step_start("Configuration", ".env")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"))
    from app.config import LLM_PROVIDER, USE_FAST_LLM, GROQ_FAST_MODEL, USE_RERANKER
    active_llm = f"Groq ({GROQ_FAST_MODEL})" if USE_FAST_LLM else f"{LLM_PROVIDER}"
    step_done("Configuration")
    metric("LLM provider", active_llm)
    metric("USE_FAST_LLM", USE_FAST_LLM)
    metric("USE_RERANKER", USE_RERANKER)
    metric("Embedding", "nomic-embed-text (Ollama)")

    print()
    return USE_RERANKER


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — CONFIGURE LlamaIndex
# ─────────────────────────────────────────────────────────────────────────────

def configure_llm():
    section("STEP 1 — CONFIGURE LlamaIndex")
    step_start("LLM + embeddings", "loading models into LlamaIndex Settings")
    from app.llm.llm_client import configure_llamaindex_settings
    configure_llamaindex_settings()
    from llama_index.core import Settings
    step_done("LLM + embeddings")
    metric("LLM",          type(Settings.llm).__name__)
    metric("Embed model",  type(Settings.embed_model).__name__)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — CLONE REPOSITORY
# ─────────────────────────────────────────────────────────────────────────────

def clone_repo():
    section("STEP 2 — CLONE REPOSITORY")
    step_start("Git clone", REPO_URL)
    from app.ingestion.repo_loader import load_repository
    repo_path = load_repository(REPO_URL)
    elapsed = step_done("Git clone")
    metric("Local path",  repo_path)
    metric("Clone time",  f"{elapsed:.2f}s")
    return repo_path


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — FILTER FILES
# ─────────────────────────────────────────────────────────────────────────────

def filter_repo(repo_path: str):
    section("STEP 3 — FILTER CODE FILES")
    step_start("File filter", "walking repository tree")
    from app.ingestion.file_filter import filter_files, VALID_EXTENSIONS, IGNORE_DIRS
    valid_files = filter_files(repo_path)
    elapsed = step_done("File filter")

    if not valid_files:
        step_fail("File filter", "No valid code files found!")
        sys.exit(1)

    # Group by extension
    ext_counts = {}
    for f in valid_files:
        ext = os.path.splitext(f)[1].lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    metric("Valid files found",  len(valid_files))
    metric("Filter time",        f"{elapsed:.2f}s")
    divider()

    print(f"     {DIM}│  Extension breakdown:{RESET}")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        bar = "█" * count
        print(f"     {DIM}│    {ext:<12}  {bar}  {count}{RESET}")

    divider()
    print(f"     {DIM}│  Files accepted:{RESET}")
    for f in valid_files:
        rel = os.path.relpath(f, repo_path)
        size_kb = os.path.getsize(f) / 1024
        print(f"     {DIM}│    {rel:<50}  {size_kb:.1f} KB{RESET}")

    return valid_files


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — PARSE + CHUNK DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

def parse_and_chunk(valid_files: list, repo_path: str):
    section("STEP 4 — PARSE + CHUNK DOCUMENTS")

    # 4a — Build codebase context doc
    step_start("Context doc builder", "extracting file structure + symbols")
    from app.indexing.context_builder import build_codebase_context
    context_doc = build_codebase_context(valid_files, repo_path, INDEX_NAME)
    elapsed_ctx = step_done("Context doc builder")
    metric("Context doc length", f"{len(context_doc.text):,} chars")

    # 4b — Load raw documents
    step_start("Document loader", f"{len(valid_files)} files → Documents")
    from app.parsing.code_parser import load_documents
    documents = load_documents(valid_files, repo_path)
    elapsed_load = step_done("Document loader")

    if not documents:
        step_fail("Document loader", "No documents loaded")
        sys.exit(1)

    metric("Documents loaded",   len(documents))
    metric("Load time",          f"{elapsed_load:.2f}s")
    divider()
    print(f"     {DIM}│  Per-document details:{RESET}")
    for doc in documents:
        path  = doc.metadata.get("path", "?")
        fsize = doc.metadata.get("file_size", 0)
        ext   = doc.metadata.get("extension", "?")
        print(f"     {DIM}│    {path:<50}  {fsize:>6} chars  [{ext}]{RESET}")

    # 4c — Parse into chunks/nodes
    step_start("Code/text splitter", "tree-sitter per language + SentenceSplitter for MD")
    from app.parsing.code_parser import parse_documents
    nodes_from_docs = parse_documents(documents)
    elapsed_parse = step_done("Code/text splitter")

    metric("Nodes from source files",  len(nodes_from_docs))
    metric("Parse time",               f"{elapsed_parse:.2f}s")

    # 4d — Chunk the context document separately with SentenceSplitter
    step_start("Context doc splitter", "SentenceSplitter(chunk_size=768)")
    from llama_index.core.node_parser import SentenceSplitter
    ctx_splitter   = SentenceSplitter(chunk_size=768, chunk_overlap=64)
    context_nodes  = ctx_splitter.get_nodes_from_documents([context_doc])
    elapsed_ctx_split = step_done("Context doc splitter")

    metric("Context doc nodes",  len(context_nodes))
    metric("Splitter time",      f"{elapsed_ctx_split:.2f}s")

    # 4e — Combine
    all_nodes = context_nodes + nodes_from_docs
    divider()
    metric("TOTAL NODES (context + source)", len(all_nodes))

    # Per-node type breakdown
    print(f"\n     {DIM}│  Chunk details:{RESET}")
    print(f"     {DIM}│  {'#':<5}{'Source':<40}{'Chars':>8}{'Tokens~':>9}{RESET}")
    divider()
    for i, node in enumerate(all_nodes[:50]):   # cap display at 50
        path   = node.metadata.get("path", "context-doc")
        text   = node.get_content()
        chars  = len(text)
        tokens = chars // 4   # rough estimate
        print(f"     {DIM}│  {i+1:<5}{path:<40}{chars:>8}{tokens:>9}{RESET}")
    if len(all_nodes) > 50:
        print(f"     {DIM}│  ... and {len(all_nodes)-50} more nodes{RESET}")

    return all_nodes, documents


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — BUILD VECTOR INDEX (ChromaDB + Ollama embeddings)
# ─────────────────────────────────────────────────────────────────────────────

def build_indexes(all_nodes: list, documents: list):
    section("STEP 5 — BUILD VECTOR INDEX  (ChromaDB + nomic-embed-text)")
    print(f"  {DIM}  This embeds all {len(all_nodes)} chunks. Progress bar below:{RESET}\n")

    step_start("VectorStoreIndex", f"embedding {len(all_nodes)} nodes → ChromaDB")
    from app.indexing.index_builder import build_vector_index, build_bm25_retriever
    vector_index = build_vector_index(all_nodes, INDEX_NAME)
    elapsed_vec = step_done("VectorStoreIndex")
    metric("Nodes embedded",    len(all_nodes))
    metric("Embedding time",    f"{elapsed_vec:.2f}s")
    metric("ChromaDB path",     f"data/index/{INDEX_NAME}/chroma/")

    # Build BM25
    step_start("BM25Retriever", f"keyword index over {len(all_nodes)} nodes")
    from app.config import TOP_K_CHUNKS
    bm25_retriever = build_bm25_retriever(all_nodes, top_k=TOP_K_CHUNKS)
    elapsed_bm25 = step_done("BM25Retriever")
    metric("BM25 nodes",    len(all_nodes))
    metric("BM25 top_k",    TOP_K_CHUNKS)
    metric("BM25 time",     f"{elapsed_bm25:.2f}s")

    return vector_index, bm25_retriever


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

def print_pipeline_summary(file_count: int, node_count: int, all_steps_start: float):
    total_elapsed = time.time() - all_steps_start
    print(f"\n{BOLD}{GREEN}{'═'*78}{RESET}")
    print(f"{BOLD}{GREEN}  PIPELINE COMPLETE  ✓{RESET}")
    print(f"{GREEN}{'═'*78}{RESET}")
    metric("Files processed",   file_count)
    metric("Total chunks/nodes", node_count)
    metric("Total wall time",   f"{total_elapsed:.2f}s")
    print(f"{GREEN}{'═'*78}{RESET}\n")


def _handle_repl_command(raw: str, last_mode) -> bool:
    command = raw.lower()

    if command in (":quit", ":q", "exit", "quit"):
        print(f"\n{DIM}Goodbye!{RESET}\n")
        return True

    if command == ":mode":
        mode_name = last_mode.value if last_mode else "not set yet"
        print(f"  {DIM}Current query mode: {CYAN}{mode_name}{RESET}\n")
        return True

    if command == ":files":
        from app.config import REPOS_DIR
        repo_path = os.path.join(REPOS_DIR, INDEX_NAME)
        from app.ingestion.file_filter import filter_files
        files = filter_files(repo_path)
        print(f"  {DIM}Indexed files ({len(files)}):{RESET}")
        for f in files:
            print(f"    {DIM}{os.path.relpath(f, repo_path)}{RESET}")
        print()
        return True

    return False


def _build_retriever_for_mode(query_mode, vector_index, bm25_retriever, top_k_chunks: int):
    from llama_index.core.retrievers import QueryFusionRetriever
    from app.retrieval.query_router import QueryMode

    if query_mode == QueryMode.CODE_LOOKUP and bm25_retriever is not None:
        retriever = QueryFusionRetriever(
            retrievers=[
                bm25_retriever,
                vector_index.as_retriever(similarity_top_k=top_k_chunks),
            ],
            similarity_top_k=top_k_chunks,
            num_queries=1,
            mode="reciprocal_rerank",
            use_async=False,
        )
        retriever_type = f"BM25 + Dense (RRF fusion, top_k={top_k_chunks})"
        return retriever, retriever_type

    retriever = vector_index.as_retriever(similarity_top_k=top_k_chunks + 5)
    retriever_type = f"Dense only (top_k={top_k_chunks + 5})"
    return retriever, retriever_type


def _print_retrieved_nodes(nodes: list) -> None:
    divider()
    print(f"     {DIM}│  Retrieved chunks (passed to LLM):{RESET}")
    for i, node in enumerate(nodes):
        path  = node.node.metadata.get("path", "unknown")
        score = node.score or 0.0
        chars = len(node.node.get_content())
        preview = node.node.get_content()[:120].replace("\n", " ")
        print(f"     {DIM}│  [{i+1}] {CYAN}{path}{RESET}  {DIM}score={score:.4f}  {chars} chars{RESET}")
        print(f"     {DIM}│      ↳ {preview}…{RESET}")


def _build_history_string(memory) -> str:
    try:
        history_msgs = memory.get()
        history_str = ""
        for msg in history_msgs[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                history_str += f"{role.upper()}: {content}\n"
        return history_str
    except Exception:
        return ""


def _build_prompt(system_prompt: str, nodes: list, raw: str, history_str: str) -> str:
    context_str = "\n\n".join([
        f"[{n.node.metadata.get('path', 'unknown')}]\n{n.node.get_content()}"
        for n in nodes
    ])
    return (
        f"{system_prompt}\n\n"
        + (f"CONVERSATION HISTORY:\n{history_str}" if history_str else "")
        + f"Context:\n{context_str}\n\n"
        + f"Question: {raw}\n\nAnswer:"
    )


def _stream_llm_response(full_prompt: str, settings_llm):
    t_llm_start = time.time()
    full_response = ""
    try:
        stream = settings_llm.stream_complete(full_prompt)
        for chunk in stream:
            delta = chunk.delta or ""
            if delta:
                print(delta, end="", flush=True)
                full_response += delta
    except Exception as e:
        print(f"\n  {RED}LLM error: {e}{RESET}")
    return full_response, time.time() - t_llm_start


def _print_turn_latency(t_route: float, t_ret: float, t_rerank: float, t_llm: float, t_total: float, response_len: int, turn_count: int, query_mode) -> None:
    print(f"\n\n  {DIM}{'─'*68}{RESET}")
    print(f"  {DIM}⏱  Routing: {t_route*1000:.0f}ms  │  "
          f"Retrieval: {t_ret*1000:.0f}ms  │  "
          f"Rerank: {t_rerank*1000:.0f}ms  │  "
          f"LLM: {t_llm*1000:.0f}ms  │  "
          f"Total: {t_total*1000:.0f}ms{RESET}")
    print(f"  {DIM}📝  Response: {response_len:,} chars  │  "
          f"Turn: #{turn_count}  │  "
          f"Mode: {CYAN}{query_mode.value}{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6 — INTERACTIVE CHAT REPL
# ─────────────────────────────────────────────────────────────────────────────

def _classify_and_route_query(raw: str, t_query_start: float):
    """Classify query and measure routing time."""
    from app.retrieval.query_router import classify_query
    
    print(f"\n  {DIM}{'─'*68}{RESET}")
    step_start("Query routing", f'"{raw[:60]}{"…" if len(raw)>60 else ""}"')
    query_mode = classify_query(raw)
    t_route = time.time() - t_query_start
    step_done("Query routing", f"→ {CYAN}{query_mode.value.upper()}{RESET}  {DIM}({t_route*1000:.0f}ms){RESET}")
    return query_mode, t_route


def _retrieve_candidate_nodes(query_mode, query_text: str, vector_index, bm25_retriever, top_k_chunks: int):
    """Retrieve raw nodes and measure retrieval time."""
    from app.config import TOP_K_CHUNKS
    
    step_start("Retrieval", f"top_k={TOP_K_CHUNKS}")
    t_ret_start = time.time()

    retriever, retriever_type = _build_retriever_for_mode(query_mode, vector_index, bm25_retriever, top_k_chunks)
    raw_nodes = retriever.retrieve(query_text)
    t_ret = time.time() - t_ret_start
    
    step_done("Retrieval", f"{retriever_type}")
    metric("Retriever type",   retriever_type)
    metric("Raw nodes retrieved", len(raw_nodes))
    metric("Retrieval time",   f"{t_ret*1000:.0f}ms")
    
    return raw_nodes, t_ret, retriever_type


def _rerank_nodes(query_text: str, raw_nodes: list, use_cross_encoder: bool, top_k_rerank: int):
    """Rerank nodes using Cross-Encoder or score sorting."""
    from app.config import TOP_K_RERANK
    
    step_start("Reranking", f"Cross-Encoder={'ON' if use_cross_encoder else 'OFF'}")
    t_rerank_start = time.time()

    if use_cross_encoder and raw_nodes:
        from app.retrieval.reranker import rerank_with_cross_encoder
        reranked_nodes = rerank_with_cross_encoder(query_text, raw_nodes, top_k=TOP_K_RERANK)
        rerank_method = f"Cross-Encoder (BAAI/bge-reranker-base) → top {TOP_K_RERANK}"
    else:
        reranked_nodes = sorted(raw_nodes, key=lambda n: n.score or 0.0, reverse=True)[:TOP_K_RERANK]
        rerank_method = f"RRF score sort → top {TOP_K_RERANK}"

    t_rerank = time.time() - t_rerank_start
    step_done("Reranking")
    metric("Rerank method",       rerank_method)
    metric("Nodes after rerank",  len(reranked_nodes))
    metric("Rerank time",         f"{t_rerank*1000:.0f}ms")
    
    return reranked_nodes, t_rerank, rerank_method


def _generate_and_stream_response(full_prompt: str, settings_llm, query_mode):
    """Build prompt and stream LLM response."""
    divider()
    prompt_chars = len(full_prompt)
    prompt_tokens = prompt_chars // 4
    metric("Prompt length",        f"{prompt_chars:,} chars (~{prompt_tokens:,} tokens)")
    metric("System prompt mode",   query_mode.value)

    print(f"\n  {DIM}{'─'*68}{RESET}")
    print(f"  {BOLD}{GREEN}Assistant ▶{RESET}")
    print()

    full_response, t_llm = _stream_llm_response(full_prompt, settings_llm)
    return full_response, t_llm


def _process_single_query(raw: str, vector_index, bm25_retriever, memory, last_mode, turn_count: int, use_cross_encoder: bool):
    """Process a single query turn through the entire pipeline."""
    from llama_index.core import Settings
    from llama_index.core.base.llms.types import ChatMessage
    from app.retrieval.query_router import QueryMode
    from app.llm.prompts import CODE_LOOKUP_PROMPT, ARCHITECTURAL_PROMPT
    from app.config import TOP_K_CHUNKS, TOP_K_RERANK

    t_query_start = time.time()

    # Route query
    query_mode, t_route = _classify_and_route_query(raw, t_query_start)

    # Retrieve
    raw_nodes, t_ret, retriever_type = _retrieve_candidate_nodes(
        query_mode, raw, vector_index, bm25_retriever, TOP_K_CHUNKS
    )

    # Rerank
    reranked_nodes, t_rerank, rerank_method = _rerank_nodes(raw, raw_nodes, use_cross_encoder, TOP_K_RERANK)

    # Show retrieved chunks
    _print_retrieved_nodes(reranked_nodes)

    # Build and execute prompt
    system_prompt = CODE_LOOKUP_PROMPT if query_mode == QueryMode.CODE_LOOKUP else ARCHITECTURAL_PROMPT
    history_str = _build_history_string(memory)
    full_prompt = _build_prompt(system_prompt, reranked_nodes, raw, history_str)

    # Generate response
    full_response, t_llm = _generate_and_stream_response(full_prompt, Settings.llm, query_mode)
    t_total = time.time() - t_query_start

    # Update memory
    try:
        memory.put(ChatMessage(role="user", content=raw))
        memory.put(ChatMessage(role="assistant", content=full_response))
    except Exception:
        pass

    # Print latency summary
    _print_turn_latency(t_route, t_ret, t_rerank, t_llm, t_total, len(full_response), turn_count, query_mode)
    
    return query_mode


def chat_repl(vector_index, bm25_retriever, use_cross_encoder: bool):
    """Interactive chat REPL with query routing, retrieval, and generation."""
    from llama_index.core.memory import ChatMemoryBuffer

    chat_header()

    memory       = ChatMemoryBuffer.from_defaults(token_limit=4096)
    last_mode    = None
    turn_count   = 0

    while True:
        try:
            raw = input(f"{BOLD}{CYAN}You ▶ {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n{DIM}Session ended.{RESET}\n")
            break

        if not raw:
            continue

        if _handle_repl_command(raw, last_mode):
            if raw.lower() in (":quit", ":q", "exit", "quit"):
                break
            continue

        turn_count += 1
        last_mode = _process_single_query(raw, vector_index, bm25_retriever, memory, last_mode, turn_count, use_cross_encoder)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    banner()
    pipeline_start = time.time()

    # PRE-FLIGHT
    use_cross_encoder = preflight_check()

    # STEP 1 — LlamaIndex settings
    configure_llm()

    # STEP 2 — Clone
    repo_path = clone_repo()

    # STEP 3 — Filter
    valid_files = filter_repo(repo_path)

    # STEP 4 — Parse + chunk
    all_nodes, documents = parse_and_chunk(valid_files, repo_path)

    # STEP 5 — Index
    vector_index, bm25_retriever = build_indexes(all_nodes, documents)

    # Summary
    print_pipeline_summary(
        file_count=len(valid_files),
        node_count=len(all_nodes),
        all_steps_start=pipeline_start,
    )

    # STEP 6 — Chat REPL
    chat_repl(vector_index, bm25_retriever, use_cross_encoder)


if __name__ == "__main__":
    main()
