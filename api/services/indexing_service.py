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

from app.config import OLLAMA_EMBED_MODEL

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


        latest_run, previous_scores, previous_findings = supabase_service.get_health_comparison_context(
            supabase,
            repo_id=repo_id,
            user_id=user_id,
        )
        previous_overall = int(latest_run["repository_health"]) if latest_run and latest_run.get("repository_health") is not None else None

        engine = RepositoryHealthEngine()
        run_payload = engine.run(
            repo=repo,
            previous_scores=previous_scores,
            previous_findings=previous_findings,
            previous_overall_score=previous_overall,
        )

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
        models = _list_ollama_models()
        return any(m.startswith(model_name) for m in models)
    except Exception:
        return False


def _list_ollama_models() -> list[str]:
    """Return installed Ollama model names from /api/tags."""
    import httpx

    r = httpx.get("http://localhost:11434/api/tags", timeout=5)
    if r.status_code != 200:
        return []
    data = r.json()
    return [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]


def _pull_ollama_model(model_name: str) -> bool:
    """Best-effort non-streaming pull for missing Ollama models."""
    import httpx

    response = httpx.post(
        "http://localhost:11434/api/pull",
        json={"name": model_name, "stream": False},
        timeout=180,
    )
    return response.status_code == 200


def _ensure_embedding_model_available(emit, model_name: str) -> bool:
    if _check_model_available(model_name):
        return True

    emit(
        "cloning",
        f"Embedding model '{model_name}' not found. Attempting automatic Ollama pull...",
        5,
        embed_model=model_name,
    )

    try:
        pulled = _pull_ollama_model(model_name)
    except Exception as exc:
        logger.warning("Automatic Ollama model pull failed: %s", exc)
        pulled = False

    if pulled and _check_model_available(model_name):
        emit(
            "cloning",
            f"Embedding model ready: {model_name}",
            7,
            embed_model=model_name,
            embed_model_pulled=True,
        )
        return True

    available_models = _list_ollama_models()
    available = ", ".join(available_models) if available_models else "none"
    emit(
        "error",
        "Embedding model not found in Ollama.\n"
        f"Expected: {model_name}\n"
        "Run:  ollama pull nomic-embed-text",
        100,
        embed_model=model_name,
        available_ollama_models=available,
        auto_pull_attempted=True,
    )
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
    logger.debug(
        "Queueing progress event (step=%s, progress=%s, extras=%s)",
        step,
        progress,
        sorted(kwargs.keys()),
    )
    try:
        loop.call_soon_threadsafe(progress_queue.put_nowait, event)
        logger.debug("Progress event queued successfully (step=%s, progress=%s)", step, progress)
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


def _validate_staged_index(staging_dir: str, min_nodes: int = 1) -> bool:
    """Validate that the staged index has valid Chroma artifacts and manifest."""
    chroma_dir = os.path.join(staging_dir, "chroma")
    if not os.path.exists(chroma_dir):
        raise ValueError(f"Validation failed: Chroma directory missing at {chroma_dir}")
    sqlite_file = os.path.join(chroma_dir, "chroma.sqlite3")
    if not os.path.exists(sqlite_file) or os.path.getsize(sqlite_file) == 0:
        raise ValueError(f"Validation failed: chroma.sqlite3 missing or empty at {sqlite_file}")
    manifest_file = os.path.join(staging_dir, "manifest.json")
    if not os.path.exists(manifest_file):
        raise ValueError(f"Validation failed: manifest.json missing at {manifest_file}")
    return True


def _promote_staged_index(staging_index_name: str, final_index_name: str) -> None:
    """Atomically promote a staged index to final index name with collection rename and rollback on failure."""
    from app.config import INDEX_DIR
    import uuid
    import shutil
    import chromadb

    staging_dir = os.path.join(INDEX_DIR, staging_index_name)
    final_dir = os.path.join(INDEX_DIR, final_index_name)

    if not os.path.exists(staging_dir):
        raise FileNotFoundError(f"Staged index not found: {staging_dir}")

    staging_chroma_dir = os.path.join(staging_dir, "chroma")
    if os.path.exists(staging_chroma_dir):
        client = None
        try:
            client = chromadb.PersistentClient(path=staging_chroma_dir)
            existing_cols = {c.name: c for c in client.list_collections()}

            # If final_index_name already exists in staging (rare collision), delete it safely
            if final_index_name in existing_cols:
                logger.warning(
                    f"Conflicting collection '{final_index_name}' found in staging {staging_chroma_dir}; removing conflict."
                )
                client.delete_collection(name=final_index_name)

            if staging_index_name in existing_cols:
                staging_col = existing_cols[staging_index_name]
                staging_col.modify(name=final_index_name)
                logger.info(
                    f"Successfully renamed staged Chroma collection '{staging_index_name}' to '{final_index_name}'."
                )
            else:
                logger.warning(
                    f"Staging collection '{staging_index_name}' not found in {staging_chroma_dir}. Collections: {list(existing_cols.keys())}"
                )
        except Exception as ce:
            if "file is not a database" in str(ce).lower():
                logger.warning(f"Mock or non-SQLite chroma directory detected; skipping collection rename: {ce}")
            else:
                logger.error(f"Failed to rename staged Chroma collection from '{staging_index_name}' to '{final_index_name}': {ce}")
                raise
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    # 2. Release any shared client references to prevent SQLite file locking before atomic replace
    try:
        chromadb.api.client.SharedSystemClient.clear_system_cache()
    except Exception:
        pass

    backup_dir = f"{final_dir}.backup-{uuid.uuid4().hex[:8]}"
    if os.path.exists(final_dir):
        os.replace(final_dir, backup_dir)

    try:
        os.replace(staging_dir, final_dir)

        # Clear system cache again so any future client loads the new index fresh from disk
        try:
            chromadb.api.client.SharedSystemClient.clear_system_cache()
        except Exception:
            pass

        # Verify that promoted Chroma index can be loaded and collection exists
        final_chroma_dir = os.path.join(final_dir, "chroma")
        if os.path.exists(final_chroma_dir):
            verify_client = None
            try:
                verify_client = chromadb.PersistentClient(path=final_chroma_dir)
                promoted_cols = [c.name for c in verify_client.list_collections()]
                if final_index_name not in promoted_cols:
                    raise ValueError(
                        f"Promoted index validation failed: collection '{final_index_name}' missing in {promoted_cols}"
                    )
            except Exception as ve:
                if "file is not a database" in str(ve).lower():
                    logger.warning(f"Mock or non-SQLite chroma directory detected; skipping post-validation: {ve}")
                else:
                    raise
            finally:
                if verify_client is not None:
                    try:
                        verify_client.close()
                    except Exception:
                        pass

        # Cleanup backup upon confirmed success
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"Failed to promote staged index from {staging_dir} to {final_dir}: {e}")
        # Roll back: restore original active index from backup if it was moved
        if os.path.exists(backup_dir):
            try:
                try:
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
                except Exception:
                    pass
                if os.path.exists(final_dir):
                    shutil.rmtree(final_dir, ignore_errors=True)
                os.replace(backup_dir, final_dir)
                try:
                    chromadb.api.client.SharedSystemClient.clear_system_cache()
                except Exception:
                    pass
                logger.info(f"Successfully rolled back active index to {final_dir} from {backup_dir}")
            except Exception as re:
                logger.critical(f"CRITICAL: Rollback failed from {backup_dir} to {final_dir}: {re}")
        raise


def _run_pipeline_sync(source: str, emit) -> Optional[dict]:
    # Emit immediately so UI never appears stalled while pre-flight checks/imports run.
    emit("cloning", "Preparing indexing environment...", 1)

    if not _check_ollama_running():
        emit(
            "error",
            "Ollama is not running.\n"
            "Start it with:  ollama serve\n"
            "Then pull the model:  ollama pull nomic-embed-text",
            100,
        )
        return None

    if not _ensure_embedding_model_available(emit, OLLAMA_EMBED_MODEL):
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

    # Check if manifest exists and run incremental indexing
    from app.indexing.incremental import run_incremental_indexing
    try:
        if run_incremental_indexing(repo_path, index_name):
            emit("graph", "Updating relationship graph…", 80)
            from app.parsing.relationship_graph import RelationshipGraphBuilder
            import json
            from app.config import INDEX_DIR
            valid_files = filter_files(repo_path)
            graph_builder = RelationshipGraphBuilder(repo_path)
            graph = graph_builder.build_graph(valid_files)
            graph_dir = os.path.join(INDEX_DIR, index_name)
            os.makedirs(graph_dir, exist_ok=True)
            graph_path = os.path.join(graph_dir, "relationship_graph.json")
            with open(graph_path, "w", encoding="utf-8") as gf:
                json.dump(graph, gf, indent=2)

            # Invalidate cached retrievers so subsequent queries use updated contents
            from app.services.qa_service import invalidate_index_cache
            invalidate_index_cache(index_name)

            # Determine file and node counts from updated manifest
            from app.indexing.incremental import load_manifest
            manifest = load_manifest(index_name)
            file_count = len(manifest) if manifest else len(valid_files)
            node_count = sum(len(v.get("chunk_ids", [])) for v in manifest.values()) if manifest else 0

            emit(
                "done",
                "Incremental re-indexing complete!",
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
    except Exception as ie:
        logger.warning(f"Incremental indexing failed/skipped: {ie}; falling back to full indexing.")

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

    import uuid
    import time
    context_splitter = SentenceSplitter(chunk_size=768, chunk_overlap=64)
    context_nodes = context_splitter.get_nodes_from_documents([context_doc])
    context_gen_id = f"ctx_gen_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    total_context_chunks = len(context_nodes)
    for idx, cnode in enumerate(context_nodes):
        cnode.metadata["context_generation"] = context_gen_id
        cnode.metadata["context_chunk_index"] = idx
        cnode.metadata["context_total_chunks"] = total_context_chunks
        cnode.metadata["path"] = "_codebase_context"
    nodes = context_nodes + nodes
    logger.info(f"Total nodes: {len(nodes)}")

    # Step 4 - Embed
    from app.config import INDEX_DIR
    import shutil
    is_existing = os.path.exists(os.path.join(INDEX_DIR, index_name))
    build_index_name = f"{index_name}_stage_{uuid.uuid4().hex[:8]}" if is_existing else index_name
    staging_dir = os.path.join(INDEX_DIR, build_index_name)

    if is_existing:
        from app.indexing.incremental import register_active_staging_build, unregister_active_staging_build
        register_active_staging_build(build_index_name)

    try:
        emit("embedding", f"Building embeddings for {len(nodes)} chunks…", 65)
        build_vector_index(nodes, build_index_name)

        # Build initial manifest
        from app.indexing.incremental import build_initial_manifest
        try:
            build_initial_manifest(nodes, repo_path, build_index_name)
        except Exception as me:
            logger.warning(f"Failed to build initial manifest: {me}")

        # Step 4.5 - Git History Indexing
        emit("history", "Extracting git log history…", 75)
        try:
            from app.ingestion.git_history import build_and_save_full_git_history
            build_and_save_full_git_history(valid_files, repo_path, build_index_name)
        except Exception as ge:
            logger.warning(f"Failed to build git history: {ge}", exc_info=True)

        # Step 5 - Relationship Graph
        emit("graph", "Building call and reference graph…", 80)
        try:
            from app.parsing.relationship_graph import RelationshipGraphBuilder
            graph_builder = RelationshipGraphBuilder(repo_path)
            graph_dir = os.path.join(INDEX_DIR, build_index_name)
            graph, graph_path = graph_builder.build_graph_atomic(valid_files, graph_dir)
            logger.info(f"Relationship graph saved atomically to {graph_path} with {len(graph)} symbols")
        except Exception as ge:
            logger.warning(f"Failed to build relationship graph: {ge}", exc_info=True)

        if is_existing:
            emit("activating", "Validating and activating replacement index…", 88)
            _validate_staged_index(staging_dir, min_nodes=len(nodes))
            _promote_staged_index(build_index_name, index_name)

        # Invalidate cached retrievers only after successful promotion
        from app.services.qa_service import invalidate_index_cache
        invalidate_index_cache(index_name)

    except Exception as build_err:
        if is_existing and os.path.exists(staging_dir):
            logger.warning(f"Index build failed in staging; removing staging artifacts {staging_dir}: {build_err}")
            shutil.rmtree(staging_dir, ignore_errors=True)
        raise build_err
    finally:
        if is_existing:
            unregister_active_staging_build(build_index_name)

    # Step 6 - Done
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


def _extract_clone_error_context(error: Exception) -> dict:
    clone_source = getattr(error, "clone_source", None)
    clone_target_path = getattr(error, "clone_target_path", None)
    if not clone_source and not clone_target_path:
        return {}
    context = {}
    if clone_source:
        context["clone_source"] = clone_source
    if clone_target_path:
        context["clone_target_path"] = clone_target_path
    return context


def _format_indexing_error_message(error: Exception, context: dict) -> str:
    message = str(error)
    clone_source = context.get("clone_source")
    clone_target_path = context.get("clone_target_path")
    details = []
    if clone_source:
        details.append(f"clone_source={clone_source}")
    if clone_target_path:
        details.append(f"clone_target_path={clone_target_path}")
    if not details:
        return message
    return f"{message}\n" + "\n".join(details)


async def run_indexing_pipeline(
    source: str,
    repo_id: str,
    progress_queue: asyncio.Queue,
) -> Optional[dict]:
    loop = asyncio.get_event_loop()
    logger.debug("Starting run_indexing_pipeline (repo_id=%s)", repo_id)

    def emit(step: str, message: str, progress: int, **kwargs):
        logger.debug(
            "Emit requested from pipeline thread (repo_id=%s, step=%s, progress=%s, extras=%s)",
            repo_id,
            step,
            progress,
            sorted(kwargs.keys()),
        )
        _emit_progress_event(loop, progress_queue, step, message, progress, **kwargs)

    def _run_pipeline():
        try:
            return _run_pipeline_sync(source, emit)

        except Exception as e:
            logger.error(f"Indexing pipeline failed: {e}", exc_info=True)
            context = _extract_clone_error_context(e)
            emit("error", _format_indexing_error_message(e, context), 100, **context)
            return None

    try:
        result = await loop.run_in_executor(None, _run_pipeline)
        logger.debug(
            "run_in_executor completed (repo_id=%s, has_result=%s)",
            repo_id,
            result is not None,
        )
    except Exception as e:
        # Safety net: if _run_pipeline raised despite all internal guards,
        # emit the error so the SSE generator doesn't hang on queue.get().
        logger.error(f"run_in_executor raised unexpectedly: {e}", exc_info=True)
        try:
            context = _extract_clone_error_context(e)
            loop.call_soon_threadsafe(
                progress_queue.put_nowait,
                {
                    "step": "error",
                    "message": _format_indexing_error_message(e, context),
                    "progress": 100,
                    **context,
                },
            )
        except Exception:
            pass
        result = None
    logger.debug("run_indexing_pipeline finished (repo_id=%s)", repo_id)
    return result


async def indexing_event_generator(
    source: str,
    repo_id: str,
    supabase,
) -> AsyncGenerator[str, None]:
    from api.services import supabase_service
    source_key = source.strip().lower()
    logger.debug("Starting indexing_event_generator (repo_id=%s, source_key=%s)", repo_id, source_key)

    # ── Check if already indexed or in-flight ──────────────────────────────────
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        logger.debug("Repository lookup failed in indexing stream (repo_id=%s)", repo_id)
        yield f"data: {json.dumps({'step': 'error', 'message': 'Repository not found.', 'progress': 0})}\n\n"
        return

    # If already successfully indexed, return the existing index metadata
    if repo["status"] == "ready":
        logger.info(f"Repository {repo_id} is already indexed. Returning existing metadata.")
        ready_event = _build_existing_repo_done_event(repo)
        logger.debug("Yielding cached ready event (repo_id=%s)", repo_id)
        yield f"data: {json.dumps(ready_event)}\n\n"
        return

    # If currently being indexed by another request, reject with 409-like error
    if repo_id in _indexing_in_flight:
        logger.warning(f"Indexing already in progress for repo {repo_id}. Rejecting concurrent attempt.")
        in_flight_event = _build_inflight_event("repository")
        logger.debug("Yielding in-flight repository event (repo_id=%s)", repo_id)
        yield f"data: {json.dumps(in_flight_event)}\n\n"
        return

    if source_key in _indexing_sources_in_flight:
        logger.warning(f"Indexing already in progress for source {source}. Rejecting concurrent attempt.")
        in_flight_source_event = _build_inflight_event("source")
        logger.debug("Yielding in-flight source event (repo_id=%s, source_key=%s)", repo_id, source_key)
        yield f"data: {json.dumps(in_flight_source_event)}\n\n"
        return

    # Mark this repo as in-flight
    _indexing_in_flight.add(repo_id)
    _indexing_sources_in_flight.add(source_key)
    logger.debug(
        "Marked indexing in-flight (repo_id=%s, in_flight_count=%s, source_in_flight_count=%s)",
        repo_id,
        len(_indexing_in_flight),
        len(_indexing_sources_in_flight),
    )

    # First event is emitted before pipeline thread starts to avoid a silent 0% UI.
    bootstrap_event = {
        "step": "cloning",
        "message": "Initialising indexing stream...",
        "progress": 1,
    }
    logger.debug("Yielding bootstrap event (repo_id=%s)", repo_id)
    yield f"data: {json.dumps(bootstrap_event)}\n\n"

    progress_queue: asyncio.Queue = asyncio.Queue()

    indexing_task = asyncio.ensure_future(
        run_indexing_pipeline(source, repo_id, progress_queue)
    )
    logger.debug("Spawned indexing pipeline task (repo_id=%s)", repo_id)

    try:
        while True:
            try:
                # Timeout increased to 5 minutes (300.0 seconds)
                logger.debug("Waiting for progress event (repo_id=%s, timeout_s=300)", repo_id)
                event = await asyncio.wait_for(progress_queue.get(), timeout=300.0)
                logger.debug(
                    "Received progress event (repo_id=%s, step=%s, progress=%s, keys=%s)",
                    repo_id,
                    event.get("step"),
                    event.get("progress"),
                    sorted(event.keys()),
                )
            except asyncio.TimeoutError:
                timeout_event = {
                    "step": "error",
                    "message": "Indexing timed out after 5 minutes.",
                    "progress": 100,
                }
                logger.warning("Progress queue timed out (repo_id=%s)", repo_id)
                logger.debug("Yielding timeout error event (repo_id=%s)", repo_id)
                yield f"data: {json.dumps(timeout_event)}\n\n"
                try:
                    supabase_service.update_repo_status(
                        supabase, repo_id, status="failed"
                    )
                    logger.debug("Updated repository status to failed after timeout (repo_id=%s)", repo_id)
                except Exception:
                    pass
                break

            logger.debug("Yielding SSE event (repo_id=%s, step=%s)", repo_id, event.get("step"))
            yield f"data: {json.dumps(event)}\n\n"

            if event["step"] == "done":
                logger.debug("Handling done event (repo_id=%s)", repo_id)
                try:
                    supabase_service.update_repo_status(
                        supabase,
                        repo_id,
                        status="ready",
                        file_count=event.get("file_count"),
                        node_count=event.get("node_count"),
                    )
                    logger.debug("Updated repository status to ready (repo_id=%s)", repo_id)
                except Exception as db_err:
                    logger.warning(f"Failed to update repo status in DB: {db_err}")

                # Keep 30-day health trend current after each successful refresh/index.
                _try_persist_post_index_health_run(supabase, repo_id)
                break

            if event["step"] == "error":
                logger.debug("Handling error event (repo_id=%s)", repo_id)
                try:
                    index_name = repo.get("index_name", repo.get("name", "repo"))
                    from app.config import INDEX_DIR
                    has_prior_index = os.path.exists(os.path.join(INDEX_DIR, index_name, "chroma", "chroma.sqlite3"))
                    new_status = "ready" if has_prior_index else "failed"
                    supabase_service.update_repo_status(
                        supabase, repo_id, status=new_status
                    )
                    logger.debug("Updated repository status to %s (has_prior_index=%s, repo_id=%s)", new_status, has_prior_index, repo_id)
                except Exception:
                    pass
                break

    finally:
        if not indexing_task.done():
            logger.debug("Cancelling unfinished indexing task (repo_id=%s)", repo_id)
            indexing_task.cancel()
        # Always remove from in-flight set when done
        _indexing_in_flight.discard(repo_id)
        _indexing_sources_in_flight.discard(source_key)
        logger.debug(
            "Cleared in-flight markers (repo_id=%s, in_flight_count=%s, source_in_flight_count=%s)",
            repo_id,
            len(_indexing_in_flight),
            len(_indexing_sources_in_flight),
        )
