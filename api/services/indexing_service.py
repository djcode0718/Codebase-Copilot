# """
# api/services/indexing_service.py
# """

# import asyncio
# import time
# import os
# import json
# from typing import AsyncGenerator, Optional

# from app.config import LLM_PROVIDER, REPOS_DIR
# from app.utils.logger import get_logger

# logger = get_logger(__name__)


# # FIX: pre-flight check before starting the pipeline.
# # If Ollama isn't running, the error was a raw Python traceback
# # ("Connection refused: ('localhost', 11434)") shown directly to the user.
# # Now we detect it early and emit a clear, actionable message.
# def _check_ollama_running() -> bool:
#     """Returns True if Ollama is reachable on localhost:11434."""
#     try:
#         import httpx
#         r = httpx.get("http://localhost:11434/api/tags", timeout=3)
#         return r.status_code == 200
#     except Exception:
#         return False


# def _check_model_available(model_name: str = "nomic-embed-text") -> bool:
#     """Returns True if the given model is pulled in Ollama."""
#     try:
#         import httpx
#         r = httpx.get("http://localhost:11434/api/tags", timeout=3)
#         if r.status_code != 200:
#             return False
#         data = r.json()
#         models = [m.get("name", "") for m in data.get("models", [])]
#         # match prefix — "nomic-embed-text" matches "nomic-embed-text:latest"
#         return any(m.startswith(model_name) for m in models)
#     except Exception:
#         return False


# async def run_indexing_pipeline(
#     source: str,
#     repo_id: str,
#     progress_queue: asyncio.Queue,
# ) -> Optional[dict]:
#     loop = asyncio.get_event_loop()

#     def emit(step: str, message: str, progress: int, **kwargs):
#         event = {"step": step, "message": message, "progress": progress, **kwargs}
#         try:
#             loop.call_soon_threadsafe(progress_queue.put_nowait, event)
#         except Exception as e:
#             logger.warning(f"Failed to emit progress event: {e}")

#     def _run_pipeline():
#         # FIX: check Ollama BEFORE importing llamaindex settings,
#         # which would itself throw an opaque connection error.
#         if not _check_ollama_running():
#             emit(
#                 "error",
#                 "Ollama is not running.\n"
#                 "Start it with:  ollama serve\n"
#                 "Then pull the model:  ollama pull nomic-embed-text",
#                 100,
#             )
#             return None

#         if not _check_model_available("nomic-embed-text"):
#             emit(
#                 "error",
#                 "Embedding model not found in Ollama.\n"
#                 "Run:  ollama pull nomic-embed-text",
#                 100,
#             )
#             return None

#         from app.llm.llm_client import configure_llamaindex_settings
#         configure_llamaindex_settings()

#         from app.ingestion.repo_loader import load_repository
#         from app.ingestion.file_filter import filter_files
#         from app.parsing.code_parser import load_documents, parse_documents
#         from app.indexing.context_builder import build_codebase_context
#         from app.indexing.index_builder import build_vector_index, build_summary_index
#         from llama_index.core.node_parser import SentenceSplitter

#         try:
#             # Step 1 — Clone
#             emit("cloning", "Cloning repository…", 10)
#             repo_path = load_repository(source)
#             index_name = os.path.basename(os.path.normpath(repo_path))

#             # Step 2 — Filter
#             emit("filtering", "Filtering source files…", 20)
#             valid_files = filter_files(repo_path)
#             if not valid_files:
#                 emit("error", "No valid code files found in this repository.", 100)
#                 return None
#             logger.info(f"Found {len(valid_files)} valid files")

#             # Step 3 — Parse
#             emit("parsing", f"Parsing {len(valid_files)} files…", 40)
#             context_doc = build_codebase_context(valid_files, repo_path, index_name)
#             documents = load_documents(valid_files, repo_path)
#             if not documents:
#                 emit("error", "No documents could be loaded.", 100)
#                 return None
#             nodes = parse_documents(documents)
#             if not nodes:
#                 emit("error", "No nodes generated from documents.", 100)
#                 return None

#             context_splitter = SentenceSplitter(chunk_size=768, chunk_overlap=64)
#             context_nodes = context_splitter.get_nodes_from_documents([context_doc])
#             nodes = context_nodes + nodes
#             logger.info(f"Total nodes: {len(nodes)}")

#             # Step 4 — Embed
#             emit(
#                 "embedding",
#                 f"Building embeddings for {len(nodes)} chunks…",
#                 65,
#             )
#             build_vector_index(nodes, index_name)

#             # Step 5 — Summary index
#             # emit("indexing", "Building document summary index…", 80)
#             # build_summary_index(documents, index_name)

#             # Step 6 — Done
#             emit("summary", "Finalising architectural context…", 90)
#             file_count = len(valid_files)
#             node_count = len(nodes)

#             emit(
#                 "done",
#                 "Indexing complete!",
#                 100,
#                 index_name=index_name,
#                 file_count=file_count,
#                 node_count=node_count,
#             )

#             return {
#                 "index_name": index_name,
#                 "file_count": file_count,
#                 "node_count": node_count,
#             }

#         except Exception as e:
#             logger.error(f"Indexing pipeline failed: {e}", exc_info=True)
#             emit("error", str(e), 100)
#             return None

#     result = await loop.run_in_executor(None, _run_pipeline)
#     return result


# async def indexing_event_generator(
#     source: str,
#     repo_id: str,
#     supabase,
# ) -> AsyncGenerator[str, None]:
#     from api.services import supabase_service

#     progress_queue: asyncio.Queue = asyncio.Queue()

#     indexing_task = asyncio.ensure_future(
#         run_indexing_pipeline(source, repo_id, progress_queue)
#     )

#     try:
#         while True:
#             try:
#                 event = await asyncio.wait_for(progress_queue.get(), timeout=180.0)
#             except asyncio.TimeoutError:
#                 yield f"data: {json.dumps({'step': 'error', 'message': 'Indexing timed out after 3 minutes.'})}\\n\\n"
#                 break

#             yield f"data: {json.dumps(event)}\\n\\n"

#             if event["step"] == "done":
#                 try:
#                     supabase_service.update_repo_status(
#                         supabase,
#                         repo_id,
#                         status="ready",
#                         file_count=event.get("file_count"),
#                         node_count=event.get("node_count"),
#                     )
#                 except Exception as db_err:
#                     logger.warning(f"Failed to update repo status in DB: {db_err}")
#                 break

#             if event["step"] == "error":
#                 try:
#                     supabase_service.update_repo_status(
#                         supabase, repo_id, status="failed"
#                     )
#                 except Exception:
#                     pass
#                 break

#     finally:
#         if not indexing_task.done():
#             indexing_task.cancel()

"""
api/services/indexing_service.py
"""

import asyncio
import time
import os
import json
from typing import AsyncGenerator, Optional

from app.config import LLM_PROVIDER, REPOS_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _check_ollama_running() -> bool:
    """Returns True if Ollama is reachable on localhost:11434."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _check_model_available(model_name: str = "nomic-embed-text") -> bool:
    """Returns True if the given model is pulled in Ollama."""
    try:
        import httpx
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code != 200:
            return False
        data = r.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        return any(m.startswith(model_name) for m in models)
    except Exception:
        return False


async def run_indexing_pipeline(
    source: str,
    repo_id: str,
    progress_queue: asyncio.Queue,
) -> Optional[dict]:
    loop = asyncio.get_event_loop()

    def emit(step: str, message: str, progress: int, **kwargs):
        event = {"step": step, "message": message, "progress": progress, **kwargs}
        try:
            loop.call_soon_threadsafe(progress_queue.put_nowait, event)
        except Exception as e:
            logger.warning(f"Failed to emit progress event: {e}")

    def _run_pipeline():
        if not _check_ollama_running():
            emit(
                "error",
                "Ollama is not running.\n"
                "Start it with:  ollama serve\n"
                "Then pull the model:  ollama pull nomic-embed-text",
                100,
            )
            return None

        if not _check_model_available("nomic-embed-text"):
            emit(
                "error",
                "Embedding model not found in Ollama.\n"
                "Run:  ollama pull nomic-embed-text",
                100,
            )
            return None

        from app.llm.llm_client import configure_llamaindex_settings
        configure_llamaindex_settings()

        from app.ingestion.repo_loader import load_repository
        from app.ingestion.file_filter import filter_files
        from app.parsing.code_parser import load_documents, parse_documents
        from app.indexing.context_builder import build_codebase_context
        from app.indexing.index_builder import build_vector_index
        from llama_index.core.node_parser import SentenceSplitter

        try:
            # Step 1 — Clone
            emit("cloning", "Cloning repository…", 10)
            repo_path = load_repository(source)
            index_name = os.path.basename(os.path.normpath(repo_path))

            # Step 2 — Filter
            emit("filtering", "Filtering source files…", 20)
            valid_files = filter_files(repo_path)
            if not valid_files:
                emit("error", "No valid code files found in this repository.", 100)
                return None
            logger.info(f"Found {len(valid_files)} valid files")

            # Step 3 — Parse
            emit("parsing", f"Parsing {len(valid_files)} files…", 40)
            # FIX: build_codebase_context no longer makes LLM calls (LLM_SUMMARY_LIMIT=0)
            # so this is now just file structure + symbol extraction — very fast
            context_doc = build_codebase_context(valid_files, repo_path, index_name)
            documents = load_documents(valid_files, repo_path)
            if not documents:
                emit("error", "No documents could be loaded.", 100)
                return None
            nodes = parse_documents(documents)
            if not nodes:
                emit("error", "No nodes generated from documents.", 100)
                return None

            context_splitter = SentenceSplitter(chunk_size=768, chunk_overlap=64)
            context_nodes = context_splitter.get_nodes_from_documents([context_doc])
            nodes = context_nodes + nodes
            logger.info(f"Total nodes: {len(nodes)}")

            # Step 4 — Embed
            emit(
                "embedding",
                f"Building embeddings for {len(nodes)} chunks…",
                65,
            )
            build_vector_index(nodes, index_name)

            # Step 5 — REMOVED: build_summary_index
            # DocumentSummaryIndex made one LLM API call per file — for a 20-file repo
            # that was 20 sequential Groq calls taking 30+ minutes.
            # BM25 + ColBERT reranking already handles file-level retrieval.
            # The codebase context document (embedded above) covers architectural queries.

            # Step 6 — Done
            emit("summary", "Finalising architectural context…", 90)
            file_count = len(valid_files)
            node_count = len(nodes)

            emit(
                "done",
                "Indexing complete!",
                100,
                index_name=index_name,
                file_count=file_count,
                node_count=node_count,
            )

            return {
                "index_name": index_name,
                "file_count": file_count,
                "node_count": node_count,
            }

        except Exception as e:
            logger.error(f"Indexing pipeline failed: {e}", exc_info=True)
            emit("error", str(e), 100)
            return None

    result = await loop.run_in_executor(None, _run_pipeline)
    return result


async def indexing_event_generator(
    source: str,
    repo_id: str,
    supabase,
) -> AsyncGenerator[str, None]:
    from api.services import supabase_service

    progress_queue: asyncio.Queue = asyncio.Queue()

    indexing_task = asyncio.ensure_future(
        run_indexing_pipeline(source, repo_id, progress_queue)
    )

    try:
        while True:
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=180.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'step': 'error', 'message': 'Indexing timed out after 3 minutes.'})}\n\n"
                break

            yield f"data: {json.dumps(event)}\n\n"

            if event["step"] == "done":
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
                    supabase_service.update_repo_status(
                        supabase, repo_id, status="failed"
                    )
                except Exception:
                    pass
                break

    finally:
        if not indexing_task.done():
            indexing_task.cancel()