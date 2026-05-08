"""
api/services/indexing_service.py
─────────────────────────────────
Wraps app/services/repo_service.process_repository() and emits granular
SSE progress events so the frontend can show a live step-by-step progress UI.

The approach: we monkey-patch key logging calls within the indexing pipeline
to emit progress events. This is the cleanest way to get real progress without
modifying the existing pipeline code.

Steps emitted:
  1. cloning     (10%)  — git clone / local path validation
  2. filtering   (20%)  — file_filter.py runs
  3. parsing     (40%)  — code_parser.py runs
  4. embedding   (65%)  — ChromaDB embedding build
  5. indexing    (80%)  — vector index written to disk
  6. summary     (90%)  — context_builder.py runs
  7. done        (100%) — pipeline complete
  8. error             — on any exception
"""

import asyncio
import time
import os
import json
import shutil
from typing import AsyncGenerator, Optional

from llama_index.core import Settings
from app.llm.llm_client import get_llm, get_embed_model
from app.config import LLM_PROVIDER, REPOS_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def run_indexing_pipeline(
    source: str,
    repo_id: str,
    progress_queue: asyncio.Queue,
) -> Optional[dict]:
    """
    Runs the full indexing pipeline in a thread (blocking I/O).
    Puts progress dicts into progress_queue as each step completes.

    Returns a dict with {index_name, file_count, node_count} on success,
    or None on failure.

    The SSE router reads from progress_queue and streams events to the client.
    """

    def emit(step: str, message: str, progress: int, **kwargs):
        """Thread-safe: put a progress event onto the asyncio queue."""
        event = {"step": step, "message": message, "progress": progress, **kwargs}
        # Use call_soon_threadsafe because this runs in a ThreadPoolExecutor
        loop.call_soon_threadsafe(progress_queue.put_nowait, event)

    loop = asyncio.get_event_loop()

    try:
        # ── Ensure LlamaIndex settings ─────────────────────────────────────
        if Settings.llm is None:
            Settings.llm = get_llm()
        if Settings.embed_model is None:
            Settings.embed_model = get_embed_model()

        # ── Step 1: Clone / validate ───────────────────────────────────────
        emit("cloning", "Cloning repository...", 10)

        from app.ingestion.repo_loader import load_repository
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: None  # warm up
        )

        try:
            repo_path = await asyncio.get_event_loop().run_in_executor(
                None, load_repository, source
            )
        except Exception as e:
            emit("error", f"Failed to clone repository: {e}", 0)
            return None

        import os as _os
        index_name = _os.path.basename(_os.path.normpath(repo_path))

        # ── Step 2: Filter files ───────────────────────────────────────────
        emit("filtering", "Scanning and filtering files...", 20)

        from app.ingestion.file_filter import filter_files
        valid_files = await asyncio.get_event_loop().run_in_executor(
            None, filter_files, repo_path
        )

        if not valid_files:
            emit("error", "No valid code files found in repository.", 0)
            return None

        file_count = len(valid_files)
        emit("filtering", f"Found {file_count} valid code files.", 25)

        # ── Step 3: Parse code ─────────────────────────────────────────────
        emit("parsing", f"Parsing {file_count} files with tree-sitter...", 40)

        from app.parsing.code_parser import load_documents, parse_documents

        documents = await asyncio.get_event_loop().run_in_executor(
            None, load_documents, valid_files, repo_path
        )

        if not documents:
            emit("error", "Failed to load documents from files.", 0)
            return None

        nodes = await asyncio.get_event_loop().run_in_executor(
            None, parse_documents, documents
        )

        if not nodes:
            emit("error", "Failed to parse documents into nodes.", 0)
            return None

        emit("parsing", f"Parsed into {len(nodes)} code chunks.", 50)

        # ── Step 4: Build architectural context ───────────────────────────
        emit("summary", "Building architectural context document...", 55)

        from app.indexing.context_builder import build_codebase_context
        context_doc = await asyncio.get_event_loop().run_in_executor(
            None, build_codebase_context, valid_files, repo_path, index_name
        )

        # Inject context doc nodes
        from llama_index.core.node_parser import SentenceSplitter
        splitter = SentenceSplitter(chunk_size=768, chunk_overlap=64)
        context_nodes = splitter.get_nodes_from_documents([context_doc])
        all_nodes = context_nodes + nodes
        node_count = len(all_nodes)

        emit("summary", f"Context document built. Total nodes: {node_count}.", 65)

        # ── Step 5: Build vector index (ChromaDB + embeddings) ─────────────
        emit("embedding", "Generating embeddings and writing to ChromaDB...", 70)

        from app.indexing.index_builder import build_vector_index
        await asyncio.get_event_loop().run_in_executor(
            None, build_vector_index, all_nodes, index_name
        )

        emit("indexing", "Vector index written to ChromaDB.", 85)

        # ── Step 6: Build DocumentSummaryIndex ────────────────────────────
        emit("indexing", "Building document summary index...", 90)

        from app.indexing.index_builder import build_summary_index
        await asyncio.get_event_loop().run_in_executor(
            None, build_summary_index, documents, index_name
        )

        # ── Done ───────────────────────────────────────────────────────────
        emit(
            "done",
            f"Ready! Indexed {file_count} files → {node_count} chunks.",
            100,
            file_count=file_count,
            node_count=node_count,
            index_name=index_name,
        )

        return {
            "index_name": index_name,
            "file_count": file_count,
            "node_count": node_count,
        }

    except Exception as e:
        logger.error(f"Indexing pipeline failed: {e}", exc_info=True)
        emit("error", f"Indexing failed: {str(e)}", 0)
        return None


async def indexing_event_generator(
    source: str,
    repo_id: str,
    supabase,
) -> AsyncGenerator[str, None]:
    """
    SSE generator for /repo/{repo_id}/index-progress.

    Yields Server-Sent Event strings:
        data: {"step": "cloning", "message": "...", "progress": 10}\\n\\n

    Also updates the Supabase repositories table as steps complete.
    """
    from api.services import supabase_service

    queue: asyncio.Queue = asyncio.Queue()

    # Start indexing in background task
    indexing_task = asyncio.create_task(
        run_indexing_pipeline(source, repo_id, queue)
    )

    # Stream progress events until done or error
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=300)
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'step': 'error', 'message': 'Indexing timed out after 5 minutes.', 'progress': 0})}\n\n"
            break

        yield f"data: {json.dumps(event)}\n\n"

        if event["step"] == "done":
            # Update Supabase with final status
            try:
                supabase_service.update_repo_status(
                    supabase,
                    repo_id,
                    status="ready",
                    file_count=event.get("file_count"),
                    node_count=event.get("node_count"),
                )
            except Exception as db_err:
                logger.warning(f"Failed to update repo status in DB: {db_err}")
            break

        if event["step"] == "error":
            try:
                supabase_service.update_repo_status(supabase, repo_id, status="failed")
            except Exception:
                pass
            break

    # Ensure the task is cleaned up
    if not indexing_task.done():
        indexing_task.cancel()
