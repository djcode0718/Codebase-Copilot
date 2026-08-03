"""
api/routers/repo.py
────────────────────
Repository endpoints:

  POST   /api/repo/index                  Start indexing a repo
  GET    /api/repo/{repo_id}/index-progress  SSE stream of indexing steps
  GET    /api/repo/list                   List all repos for user
  GET    /api/repo/{repo_id}              Get a single repo's status
  DELETE /api/repo/{repo_id}              Delete a repo + its index from disk
"""

import os
import shutil
import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.repo import IndexRepoRequest, IndexRepoResponse, RepoStatusResponse
from api.services import supabase_service
from api.services.indexing_service import indexing_event_generator
from app.config import LLM_PROVIDER, INDEX_DIR, REPOS_DIR
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/index", response_model=IndexRepoResponse)
async def index_repository(
    body: IndexRepoRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Step 1: Create a repository record in Supabase with status='indexing'.
    The actual indexing happens when the client opens the SSE stream
    at /api/repo/{repo_id}/index-progress.

    This endpoint returns immediately with the repo_id so the client
    can open the SSE connection right away.
    """
    # Derive a name from the source URL / path
    source = body.source
    if source.startswith("http"):
        name = source.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
    else:
        name = os.path.basename(os.path.normpath(source))

    # Create DB record
    repo_record = supabase_service.create_repo_record(
        supabase,
        user_id=user_id,
        name=name,
        source_url=source,
        index_name=name,       # will be confirmed/corrected once cloned
        llm_provider=LLM_PROVIDER,
    )

    return IndexRepoResponse(
        repo_id=repo_record["id"],
        index_name=name,
        status="indexing",
        message="Repository record created. Open the SSE stream to start indexing.",
    )


@router.get("/{repo_id}/index-progress")
async def index_progress(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    SSE stream that runs the actual indexing pipeline and emits step events.

    The client opens this with EventSource or fetch+ReadableStream.
    Events format:
        data: {"step": "cloning", "message": "...", "progress": 10}

    Final events:
        data: {"step": "done", "progress": 100, "file_count": 47, "node_count": 312}
        data: {"step": "error", "message": "..."}
    """
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    source = repo["source_url"]

    return StreamingResponse(
        indexing_event_generator(source, repo_id, supabase),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disables nginx buffering
        },
    )


@router.get("/list", response_model=List[RepoStatusResponse])
async def list_repositories(
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Return all repositories indexed by this user, newest first."""
    repos = supabase_service.get_repos_for_user(supabase, user_id)
    return [RepoStatusResponse(**r) for r in repos]


@router.get("/{repo_id}", response_model=RepoStatusResponse)
async def get_repository(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Get a single repository's status and metadata."""
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return RepoStatusResponse(**repo)


@router.delete("/{repo_id}")
async def delete_repository(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Delete a repository:
    - Removes the DB record (cascades to chats + messages)
    - Removes the ChromaDB index directory from disk
    - Removes the cloned repo from data/repos/
    """
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    index_name = repo["index_name"]

    # Remove from disk (best-effort — don't fail if already gone)
    index_path = os.path.join(INDEX_DIR, index_name)
    if os.path.exists(index_path):
        try:
            shutil.rmtree(index_path)
            logger.info(f"Removed index directory: {index_path}")
            
            # Clear ChromaDB's internal cache. 
            # If we delete the directory while the singleton client holds an open SQLite handle,
            # re-indexing the same repo immediately throws a "readonly database" error.
            import chromadb
            chromadb.api.client.SharedSystemClient.clear_system_cache()
            
        except Exception as e:
            logger.warning(f"Could not remove index dir {index_path}: {e}")

    repo_path = os.path.join(REPOS_DIR, index_name)
    if os.path.exists(repo_path):
        try:
            shutil.rmtree(repo_path)
            logger.info(f"Removed repo directory: {repo_path}")
        except Exception as e:
            logger.warning(f"Could not remove repo dir {repo_path}: {e}")

    # Remove from DB (cascades to chats/messages via FK)
    supabase_service.delete_repo(supabase, repo_id)

    return {"message": f"Repository '{index_name}' deleted successfully."}
