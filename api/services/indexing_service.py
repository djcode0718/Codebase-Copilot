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
import os
import json
from typing import AsyncGenerator, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

_indexing_in_flight: set = set()
_indexing_sources_in_flight: set = set()


def _try_persist_post_index_health_run(supabase, repo_id: str) -> None:
    """Best-effort health snapshot after indexing completes.

    This keeps the 30-day trend chart fresh even when users only run
    repository refresh/index flows and do not manually click "Run Health Analysis".
    """
    try:
        from api.services import supabase_service
        from api.services.repository_health_engine import RepositoryHealthEngine

        repo = supabase_service.get_repo(supabase, repo_id)
        if not repo:
            return

        user_id = repo.get("user_id")
        if not user_id:
            return

        if not supabase_service.is_repository_health_schema_available(supabase):
            return

        previous_run = supabase_service.get_latest_health_run(supabase, repo_id=repo_id, user_id=user_id)
        previous_scores = None
        previous_findings = None
        if previous_run:
            previous_scores = supabase_service.get_health_category_score_map(
                supabase,
                run_id=previous_run["id"],
                user_id=user_id,
            )
            previous_findings = supabase_service.get_health_problem_titles(
                supabase,
                run_id=previous_run["id"],
                user_id=user_id,
            )

        engine = RepositoryHealthEngine()
        run_payload = engine.run(repo=repo, previous_scores=previous_scores, previous_findings=previous_findings)

        run_record = supabase_service.insert_health_run(
            supabase,
            repo_id=repo_id,
            user_id=user_id,
            top_level=run_payload["top_level"],
            executive_summary=run_payload["executive_summary"],
            strengths=run_payload["strengths"],
            weaknesses=run_payload["weaknesses"],
            critical_risks=run_payload["critical_risks"],
            architecture_risks=run_payload["architecture_risks"],
            security_risks=run_payload["security_risks"],
            performance_risks=run_payload["performance_risks"],
            recommended_sprint=run_payload["recommended_sprint"],
            improved_categories=run_payload["improved_categories"],
            declining_categories=run_payload["declining_categories"],
            new_risks=run_payload["new_risks"],
            resolved_risks=run_payload["resolved_risks"],
            benchmark=run_payload["benchmark"],
        )
        supabase_service.insert_health_category_scores(
            supabase,
            run_id=run_record["id"],
            repo_id=repo_id,
            user_id=user_id,
            categories=run_payload["categories"],
        )
        supabase_service.insert_health_findings(
            supabase,
            run_id=run_record["id"],
            repo_id=repo_id,
            user_id=user_id,
            findings=run_payload["findings"],
        )
        supabase_service.insert_health_recommendations(
            supabase,
            run_id=run_record["id"],
            repo_id=repo_id,
            user_id=user_id,
            recommendations=run_payload["recommendations"],
        )
        logger.info(f"Persisted post-index repository health run for repo_id={repo_id}")
    except Exception as e:
        logger.warning(f"Post-index health run failed for repo_id={repo_id}: {e}")


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


def _emit_progress_event(
    loop: asyncio.AbstractEventLoop,
    progress_queue: asyncio.Queue,
    step: str,
    message: str,
    progress: int,
    **kwargs,
):
    event = {"step": step, "message": message, "progress": progress, **kwargs}
    try:
        loop.call_soon_threadsafe(progress_queue.put_nowait, event)
    except Exception as e:
        logger.warning(f"Failed to emit progress event: {e}")


def _load_pipeline_dependencies(emit):
    try:
        from app.llm.llm_client import configure_llamaindex_settings

        configure_llamaindex_settings()
    except ModuleNotFoundError as e:
        emit(
            "error",
            f"Missing Python dependency: {e}\n"
            "Install LlamaIndex with:\n"
            "  pip install -r requirements-llamaindex.txt\n"
            "or:\n"
            "  pip install llama-index llama-index-llms-groq llama-index-embeddings-ollama",
            100,
        )
        return None

    try:
        from app.ingestion.repo_loader import load_repository
        from app.ingestion.file_filter import filter_files
        from app.parsing.code_parser import load_documents, parse_documents
        from app.indexing.context_builder import build_codebase_context
        from app.indexing.index_builder import build_vector_index
        from llama_index.core.node_parser import SentenceSplitter
    except ModuleNotFoundError as e:
        emit(
            "error",
            f"Missing Python dependency: {e}\n"
            "Install with:  pip install -r requirements-llamaindex.txt",
            100,
        )
        return None

    return (
        load_repository,
        filter_files,
        load_documents,
        parse_documents,
        build_codebase_context,
        build_vector_index,
        SentenceSplitter,
    )


def _run_pipeline_sync(source: str, emit) -> Optional[dict]:
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

    pipeline_dependencies = _load_pipeline_dependencies(emit)
    if pipeline_dependencies is None:
        return None

    (
        load_repository,
        filter_files,
        load_documents,
        parse_documents,
        build_codebase_context,
        build_vector_index,
        SentenceSplitter,
    ) = pipeline_dependencies

    # Step 1 - Clone
    emit("cloning", "Cloning repository…", 10)
    repo_path = load_repository(source)
    index_name = os.path.basename(os.path.normpath(repo_path))

    # Step 2 - Filter
    emit("filtering", "Filtering source files…", 20)
    valid_files = filter_files(repo_path)
    if not valid_files:
        emit("error", "No valid code files found in this repository.", 100)
        return None
    logger.info(f"Found {len(valid_files)} valid files")

    # Step 3 - Parse
    emit("parsing", f"Parsing {len(valid_files)} files…", 40)
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

    # Step 4 - Embed
    emit("embedding", f"Building embeddings for {len(nodes)} chunks…", 65)
    build_vector_index(nodes, index_name)

    # Step 5 - Done
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


def _build_existing_repo_done_event(repo: dict) -> dict:
    return {
        "step": "done",
        "message": f"Repository already indexed: {repo.get('file_count', 0)} files, {repo.get('node_count', 0)} chunks.",
        "progress": 100,
        "file_count": repo.get("file_count", 0),
        "node_count": repo.get("node_count", 0),
        "index_name": repo.get("index_name", ""),
    }


def _build_inflight_event(scope: str) -> dict:
    return {
        "step": "error",
        "message": f"Indexing already in progress for this {scope}. Please wait for it to complete.",
        "progress": 0,
    }


async def run_indexing_pipeline(
    source: str,
    repo_id: str,
    progress_queue: asyncio.Queue,
) -> Optional[dict]:
    loop = asyncio.get_event_loop()

    def emit(step: str, message: str, progress: int, **kwargs):
        _emit_progress_event(loop, progress_queue, step, message, progress, **kwargs)

    def _run_pipeline():
        try:
            return _run_pipeline_sync(source, emit)

        except Exception as e:
            logger.error(f"Indexing pipeline failed: {e}", exc_info=True)
            emit("error", str(e), 100)
            return None

    try:
        result = await loop.run_in_executor(None, _run_pipeline)
    except Exception as e:
        # Safety net: if _run_pipeline raised despite all internal guards,
        # emit the error so the SSE generator doesn't hang on queue.get().
        logger.error(f"run_in_executor raised unexpectedly: {e}", exc_info=True)
        try:
            loop.call_soon_threadsafe(
                progress_queue.put_nowait,
                {"step": "error", "message": str(e), "progress": 100},
            )
        except Exception:
            pass
        result = None
    return result


async def indexing_event_generator(
    source: str,
    repo_id: str,
    supabase,
) -> AsyncGenerator[str, None]:
    from api.services import supabase_service
    source_key = source.strip().lower()

    # ── Check if already indexed or in-flight ──────────────────────────────────
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        yield f"data: {json.dumps({'step': 'error', 'message': 'Repository not found.', 'progress': 0})}\n\n"
        return

    # If already successfully indexed, return the existing index metadata
    if repo["status"] == "ready":
        logger.info(f"Repository {repo_id} is already indexed. Returning existing metadata.")
        ready_event = _build_existing_repo_done_event(repo)
        yield f"data: {json.dumps(ready_event)}\n\n"
        return

    # If currently being indexed by another request, reject with 409-like error
    if repo_id in _indexing_in_flight:
        logger.warning(f"Indexing already in progress for repo {repo_id}. Rejecting concurrent attempt.")
        in_flight_event = _build_inflight_event("repository")
        yield f"data: {json.dumps(in_flight_event)}\n\n"
        return

    if source_key in _indexing_sources_in_flight:
        logger.warning(f"Indexing already in progress for source {source}. Rejecting concurrent attempt.")
        in_flight_source_event = _build_inflight_event("source")
        yield f"data: {json.dumps(in_flight_source_event)}\n\n"
        return

    # Mark this repo as in-flight
    _indexing_in_flight.add(repo_id)
    _indexing_sources_in_flight.add(source_key)

    progress_queue: asyncio.Queue = asyncio.Queue()

    indexing_task = asyncio.ensure_future(
        run_indexing_pipeline(source, repo_id, progress_queue)
    )

    try:
        while True:
            try:
                # Timeout increased to 5 minutes (300.0 seconds)
                event = await asyncio.wait_for(progress_queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                timeout_event = {
                    "step": "error",
                    "message": "Indexing timed out after 5 minutes.",
                    "progress": 100,
                }
                yield f"data: {json.dumps(timeout_event)}\n\n"
                try:
                    supabase_service.update_repo_status(
                        supabase, repo_id, status="failed"
                    )
                except Exception:
                    pass
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

                # Keep 30-day health trend current after each successful refresh/index.
                _try_persist_post_index_health_run(supabase, repo_id)
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
        # Always remove from in-flight set when done
        _indexing_in_flight.discard(repo_id)
        _indexing_sources_in_flight.discard(source_key)
