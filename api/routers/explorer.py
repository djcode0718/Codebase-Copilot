"""Repository Explorer endpoints (additive to existing repository workflows)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.explorer import (
    ExplorerConversationEntryRequest,
    ExplorerFileResponse,
    ExplorerFixApplyRequest,
    ExplorerFixGenerateRequest,
    ExplorerReviewFileRequest,
    ExplorerReviewFilesRequest,
    ExplorerTestDiscoverRequest,
    ExplorerTestRunRequest,
    ExplorerTreeResponse,
)
from api.services import supabase_service
from api.services import repository_explorer_service as explorer_service

router = APIRouter()


def _ensure_repo_access(supabase: Client, user_id: str, repo_id: str) -> dict:
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return repo


@router.get("/{repo_id}/explorer/tree", response_model=ExplorerTreeResponse)
async def list_repository_tree(
    repo_id: str,
    path: str = Query(default="", description="Relative folder path"),
    include_hidden: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    try:
        payload = await asyncio.to_thread(
            explorer_service.list_directory_tree,
            repo,
            relative_path=path,
            include_hidden=include_hidden,
            limit=limit,
        )
        return ExplorerTreeResponse(**payload)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.get("/{repo_id}/explorer/file", response_model=ExplorerFileResponse)
async def get_repository_file(
    repo_id: str,
    path: str = Query(..., description="Relative file path"),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    try:
        payload = await asyncio.to_thread(explorer_service.get_file_details, repo, relative_path=path)
        return ExplorerFileResponse(**payload)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{repo_id}/explorer/review/file")
async def review_repository_file(
    repo_id: str,
    body: ExplorerReviewFileRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    prompt = (body.prompt or "").strip()
    if body.review_type and body.review_type != "review":
        prompt = f"[{body.review_type}] {prompt}".strip()

    result = await asyncio.to_thread(
        explorer_service.review_single_file,
        repo,
        relative_path=body.path,
        prompt=prompt,
    )
    return result


@router.post("/{repo_id}/explorer/review/files")
async def review_repository_files(
    repo_id: str,
    body: ExplorerReviewFilesRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    prompt = (body.prompt or "").strip()
    if body.review_type and body.review_type != "review":
        prompt = f"[{body.review_type}] {prompt}".strip()

    result = await asyncio.to_thread(
        explorer_service.review_multiple_files,
        repo,
        relative_paths=body.paths,
        prompt=prompt,
    )
    return result


@router.post("/{repo_id}/explorer/fix/generate")
async def generate_repository_fix(
    repo_id: str,
    body: ExplorerFixGenerateRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    return await asyncio.to_thread(
        explorer_service.generate_fix_proposal,
        repo,
        relative_path=body.path,
        finding=body.finding,
        recommendation=body.recommendation,
    )


@router.post("/{repo_id}/explorer/fix/apply")
async def apply_repository_fix(
    repo_id: str,
    body: ExplorerFixApplyRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    try:
        return await asyncio.to_thread(
            explorer_service.apply_fix_proposal,
            repo,
            fix_id=body.fix_id,
            expected_sha256=body.expected_sha256,
            run_validation=body.run_validation,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Fix proposal not found")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err


@router.post("/{repo_id}/explorer/tests/discover")
async def discover_repository_tests(
    repo_id: str,
    body: ExplorerTestDiscoverRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    return await asyncio.to_thread(
        explorer_service.discover_impacted_tests,
        repo,
        relative_paths=body.paths,
    )


@router.post("/{repo_id}/explorer/tests/run")
async def run_repository_tests(
    repo_id: str,
    body: ExplorerTestRunRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    return await asyncio.to_thread(
        explorer_service.run_targeted_tests,
        repo,
        tests=body.tests,
        timeout_seconds=body.timeout_seconds,
    )


@router.get("/{repo_id}/explorer/history")
async def get_explorer_history(
    repo_id: str,
    path: str = Query(..., min_length=1),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    return explorer_service.get_file_history(repo_id, path)


@router.post("/{repo_id}/explorer/conversations")
async def add_explorer_conversation_entry(
    repo_id: str,
    body: ExplorerConversationEntryRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    return explorer_service.append_conversation_entry(repo_id, body.path, body.role, body.content)

