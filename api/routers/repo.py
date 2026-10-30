"""
api/routers/repo.py
────────────────────
Repository endpoints:

  POST   /api/repo/index                     Start indexing a repo
  POST   /api/repo/{repo_id}/refresh         Reset and re-index an existing repo
  GET    /api/repo/{repo_id}/index-progress  SSE stream of indexing steps
  GET    /api/repo/list                      List all repos for user
  GET    /api/repo/{repo_id}                 Get a single repo's status
  DELETE /api/repo/{repo_id}                 Delete a repo + its index from disk
"""

import os
import shutil
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.repo import (
    IndexRepoRequest,
    IndexRepoResponse,
    RepoStatusResponse,
    BranchCheckoutRequest,
    BranchPullRequest,
    BranchListResponse,
    BranchStatusResponse,
    BranchActionResponse,
    BranchComparisonResponse,
)
from api.routers._repo_access import ensure_repo_access
from api.services import supabase_service, repo_branch_service
from api.services.indexing_service import indexing_event_generator
from app.ingestion.repo_naming import derive_repo_name
from app.config import LLM_PROVIDER, INDEX_DIR, REPOS_DIR
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _build_branch_status_response(repo: dict, status: dict) -> BranchStatusResponse:
    return BranchStatusResponse(
        current_branch=status.get("current_branch", "unknown"),
        default_branch=status.get("default_branch", "main"),
        last_commit=status.get("last_commit", ""),
        author=status.get("author", ""),
        commit_sha=status.get("commit_sha", "unknown"),
        short_commit_sha=status.get("short_commit_sha", "unknown"),
        ahead=int(status.get("ahead", 0) or 0),
        behind=int(status.get("behind", 0) or 0),
        changed_files=int(status.get("changed_files", 0) or 0),
        files_added=int(status.get("files_added", 0) or 0),
        files_modified=int(status.get("files_modified", 0) or 0),
        files_deleted=int(status.get("files_deleted", 0) or 0),
        changed_paths=list(status.get("changed_paths") or []),
        captured_at=status.get("captured_at", ""),
        indexed_at=status.get("indexed_at"),
        index_status=status.get("index_status", "unknown"),
        evaluation_status=status.get("evaluation_status", "unknown"),
        health_score=status.get("health_score"),
        sync_status=status.get("sync_status", "unknown"),
    )


def _enrich_branch_status_with_repo_metrics(supabase: Client, repo_id: str, status: dict) -> dict:
    out = dict(status)
    try:
        latest_eval = supabase_service.get_latest_evaluation(supabase, repo_id)
        out["evaluation_status"] = "ready" if latest_eval else "not_run"
    except Exception:
        out["evaluation_status"] = "unknown"

    try:
        repo = supabase_service.get_repo(supabase, repo_id)
        user_id = (repo or {}).get("user_id")
        if user_id:
            latest_health = supabase_service.get_latest_health_run(supabase, repo_id=repo_id, user_id=user_id)
            if latest_health:
                out["health_score"] = latest_health.get("repository_health")
    except Exception:
        out["health_score"] = None

    return out


def _remove_repo_artifacts(index_name: str) -> None:
    """Best-effort cleanup before delete/refresh to avoid stale index artifacts."""
    index_path = os.path.join(INDEX_DIR, index_name)
    if os.path.exists(index_path):
        try:
            shutil.rmtree(index_path)
            logger.info(f"Removed index directory: {index_path}")

            # Prevent stale SQLite handles in Chroma singleton after directory deletion.
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

    existing_inflight = supabase_service.get_inflight_repo_for_source(
        supabase,
        user_id=user_id,
        source_url=source,
    )
    if existing_inflight:
        return IndexRepoResponse(
            repo_id=existing_inflight["id"],
            index_name=existing_inflight.get("index_name", existing_inflight.get("name", "repo")),
            status="indexing",
            message="Repository is already being indexed. Reusing the active indexing session.",
        )

    name = derive_repo_name(source)

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


import threading

_REFRESH_LOCKS: dict[str, threading.Lock] = {}
_REFRESH_LOCKS_GUARD = threading.Lock()


def _get_refresh_lock(repo_id: str) -> threading.Lock:
    with _REFRESH_LOCKS_GUARD:
        if repo_id not in _REFRESH_LOCKS:
            _REFRESH_LOCKS[repo_id] = threading.Lock()
        return _REFRESH_LOCKS[repo_id]


@router.post("/{repo_id}/refresh", response_model=IndexRepoResponse)
async def refresh_repository(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Reset and re-index an existing repository to capture latest source changes."""
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    lock = _get_refresh_lock(repo_id)
    if not lock.acquire(blocking=False):
        return IndexRepoResponse(
            repo_id=repo_id,
            index_name=repo.get("index_name", repo.get("name", "repo")),
            status="indexing",
            message="Repository refresh is already in progress.",
        )

    try:
        from api.services.indexing_service import _indexing_in_flight
        if repo_id in _indexing_in_flight or repo.get("status") == "indexing":
            return IndexRepoResponse(
                repo_id=repo_id,
                index_name=repo.get("index_name", repo.get("name", "repo")),
                status="indexing",
                message="Repository is already being indexed.",
            )

        index_name = repo.get("index_name", repo.get("name", "repo"))
        # B7 Fix: Never delete existing repo clone or index directory here.
        # The existing working index remains intact and queryable until a replacement
        # is cloned, parsed, embedded, and successfully activated in staging.
        supabase_service.reset_repo_for_reindex(supabase, repo_id)

        return IndexRepoResponse(
            repo_id=repo_id,
            index_name=index_name,
            status="indexing",
            message="Repository refresh started. Open the SSE stream to re-index latest changes.",
        )
    finally:
        lock.release()


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
    _remove_repo_artifacts(index_name)

    # Remove from DB (cascades to chats/messages via FK)
    supabase_service.delete_repo(supabase, repo_id)

    return {"message": f"Repository '{index_name}' deleted successfully."}


@router.get("/{repo_id}/branches", response_model=BranchListResponse)
async def list_repository_branches(
    repo_id: str,
    q: str = Query(default="", alias="query"),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        payload = repo_branch_service.list_branches(repo, query=q)
        supabase_service.update_repo_workspace_context(
            supabase,
            repo_id,
            active_branch=payload.get("current_branch"),
            default_branch=payload.get("default_branch"),
            recent_branch=payload.get("current_branch"),
        )
        context = supabase_service.get_repo_workspace_context(repo)
        recent = context.get("recent_branches") or payload.get("recent_branches") or []
        return BranchListResponse(
            current_branch=payload["current_branch"],
            default_branch=payload["default_branch"],
            recent_branches=recent[:8],
            local_branches=payload["local_branches"],
            remote_branches=payload["remote_branches"],
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{repo_id}/branches/refresh", response_model=BranchListResponse)
async def refresh_repository_branches(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        payload = repo_branch_service.list_branches(repo, query="")
        return BranchListResponse(**payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{repo_id}/branches/status", response_model=BranchStatusResponse)
async def get_repository_branch_status(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        status = repo_branch_service.get_branch_status(repo)
        status = _enrich_branch_status_with_repo_metrics(supabase, repo_id, status)
        supabase_service.update_repo_workspace_context(
            supabase,
            repo_id,
            active_branch=status.get("current_branch"),
            default_branch=status.get("default_branch"),
            active_commit_sha=status.get("commit_sha"),
            recent_branch=status.get("current_branch"),
        )
        return _build_branch_status_response(repo, status)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{repo_id}/branches/pull", response_model=BranchActionResponse)
async def pull_repository_branch(
    repo_id: str,
    body: Optional[BranchPullRequest] = None,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        pull = repo_branch_service.pull_latest(repo, branch=(body.branch if body else None))
        status = repo_branch_service.get_branch_status(repo)
        status = _enrich_branch_status_with_repo_metrics(supabase, repo_id, status)
        supabase_service.update_repo_workspace_context(
            supabase,
            repo_id,
            active_branch=status.get("current_branch"),
            default_branch=status.get("default_branch"),
            active_commit_sha=status.get("commit_sha"),
            recent_branch=status.get("current_branch"),
        )
        return BranchActionResponse(
            message=pull.get("message", "Branch pulled."),
            current_branch=status.get("current_branch", "unknown"),
            commit_sha=status.get("commit_sha", "unknown"),
            status=_build_branch_status_response(repo, status),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{repo_id}/branches/checkout", response_model=BranchActionResponse)
async def checkout_repository_branch(
    repo_id: str,
    body: BranchCheckoutRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        result = repo_branch_service.checkout_branch(repo, body.branch, pull_after_checkout=body.pull_latest)
        status = _enrich_branch_status_with_repo_metrics(supabase, repo_id, result["status"])
        supabase_service.update_repo_workspace_context(
            supabase,
            repo_id,
            active_branch=status.get("current_branch"),
            default_branch=status.get("default_branch"),
            active_commit_sha=status.get("commit_sha"),
            recent_branch=status.get("current_branch"),
        )
        return BranchActionResponse(
            message=result.get("message", f"Checked out {body.branch}."),
            current_branch=status.get("current_branch", "unknown"),
            commit_sha=status.get("commit_sha", "unknown"),
            status=_build_branch_status_response(repo, status),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        detail = str(e)
        lowered = detail.lower()
        if "conflict" in lowered or "would be overwritten" in lowered:
            raise HTTPException(status_code=409, detail=f"Checkout blocked by local changes: {detail}")
        raise HTTPException(status_code=400, detail=detail)


@router.post("/{repo_id}/branches/return-default", response_model=BranchActionResponse)
async def return_repository_default_branch(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        result = repo_branch_service.return_to_default_branch(repo, pull_after_checkout=True)
        status = _enrich_branch_status_with_repo_metrics(supabase, repo_id, result["status"])
        supabase_service.update_repo_workspace_context(
            supabase,
            repo_id,
            active_branch=status.get("current_branch"),
            default_branch=status.get("default_branch"),
            active_commit_sha=status.get("commit_sha"),
            recent_branch=status.get("current_branch"),
        )
        return BranchActionResponse(
            message=result.get("message", "Returned to default branch."),
            current_branch=status.get("current_branch", "unknown"),
            commit_sha=status.get("commit_sha", "unknown"),
            status=_build_branch_status_response(repo, status),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{repo_id}/branches/compare", response_model=BranchComparisonResponse)
async def compare_repository_branches(
    repo_id: str,
    base_branch: str = Query(..., min_length=1),
    target_branch: str = Query(..., min_length=1),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    try:
        payload = repo_branch_service.compare_branches(repo, base_branch=base_branch, target_branch=target_branch)
        return BranchComparisonResponse(**payload)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

