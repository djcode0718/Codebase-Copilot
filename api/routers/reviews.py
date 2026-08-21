"""Engineering review endpoints."""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.review import (
    ReviewFileRequest,
    ReviewFilesRequest,
    ReviewCommitRequest,
    ReviewPullRequestRequest,
    ReviewFixRequest,
    ReviewFixResponse,
    ReviewTargetType,
    ReviewRunResponse,
    ReviewListResponse,
    ReviewHistoryItem,
)
from api.services import supabase_service
from api.services.commit_review_service import review_commit
from api.services.pull_request_review_service import review_pull_request
from api.services.review_service import review_files
from api.services.review_storage_service import store_review, list_reviews, get_review, delete_review
from api.services.review_suggestion_service import generate_fix_text

router = APIRouter()


def _normalize_target_type(value: str) -> ReviewTargetType:
    target_type = str(value or "file")
    if target_type not in {"file", "files", "commit", "pr"}:
        target_type = "file"
    return cast(ReviewTargetType, target_type)


def _ensure_repo_access(supabase: Client, user_id: str, repo_id: str) -> dict:
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return repo


def _review_analysis_context(repo: dict) -> dict:
    return {
        "repository": repo.get("name") or repo.get("id"),
        "branch": repo.get("active_branch") or repo.get("default_branch") or "unknown",
        "commit_sha": repo.get("active_commit_sha") or "unknown",
        "index_version": repo.get("index_name") or "unknown",
        "indexed_at": repo.get("indexed_at"),
    }


def _to_review_response(record: dict) -> ReviewRunResponse:
    context = dict(record.get("analysis_context") or {})
    if not context:
        request_payload = record.get("request_payload") or {}
        context = dict(request_payload.get("analysis_context") or {})
    return ReviewRunResponse(
        review_id=record["id"],
        repo_id=record["repo_id"],
        target_type=_normalize_target_type(str(record.get("target_type") or "file")),
        status=record.get("status", "completed"),
        summary=record.get("summary") or "",
        findings=record.get("findings") or [],
        changed_files=record.get("changed_files") or [],
        commit_hash=record.get("commit_hash"),
        analysis_context=context,
        created_at=record.get("created_at"),
    )


@router.post("/file", response_model=ReviewRunResponse)
async def review_file_endpoint(
    body: ReviewFileRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, body.repo_id)
    analysis_context = _review_analysis_context(repo)
    try:
        result = await review_files(repo=repo, file_paths=[body.filename], prompt=body.prompt)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"File review failed: {err}") from err
    record = store_review(
        supabase,
        repo_id=body.repo_id,
        user_id=user_id,
        target_type="file",
        summary=result["summary"],
        findings=result["findings"],
        changed_files=result["changed_files"],
        request_payload={**body.model_dump(), "analysis_context": analysis_context},
    )
    return _to_review_response(record)


@router.post("/files", response_model=ReviewRunResponse)
async def review_files_endpoint(
    body: ReviewFilesRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    if not body.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    repo = _ensure_repo_access(supabase, user_id, body.repo_id)
    analysis_context = _review_analysis_context(repo)
    try:
        result = await review_files(repo=repo, file_paths=body.files, prompt=body.prompt)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Files review failed: {err}") from err
    record = store_review(
        supabase,
        repo_id=body.repo_id,
        user_id=user_id,
        target_type="files",
        summary=result["summary"],
        findings=result["findings"],
        changed_files=result["changed_files"],
        request_payload={**body.model_dump(), "analysis_context": analysis_context},
    )
    return _to_review_response(record)


@router.post("/commit", response_model=ReviewRunResponse)
async def review_commit_endpoint(
    body: ReviewCommitRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, body.repo_id)
    analysis_context = _review_analysis_context(repo)
    try:
        result = await review_commit(repo=repo, commit_hash=body.commit_hash, prompt=body.prompt)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Commit review failed: {err}") from err
    record = store_review(
        supabase,
        repo_id=body.repo_id,
        user_id=user_id,
        target_type="commit",
        summary=result["summary"],
        findings=result["findings"],
        changed_files=result["changed_files"],
        commit_hash=body.commit_hash,
        request_payload={**body.model_dump(), "analysis_context": analysis_context},
    )
    return _to_review_response(record)


@router.post("/pr", response_model=ReviewRunResponse)
async def review_pr_endpoint(
    body: ReviewPullRequestRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, body.repo_id)
    analysis_context = _review_analysis_context(repo)
    if not body.changed_files and not body.diff.strip():
        raise HTTPException(status_code=400, detail="changed_files or diff must be provided")

    try:
        result = await review_pull_request(
            repo=repo,
            changed_files=body.changed_files,
            diff=body.diff,
            prompt=body.prompt,
        )
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"PR review failed: {err}") from err
    record = store_review(
        supabase,
        repo_id=body.repo_id,
        user_id=user_id,
        target_type="pr",
        summary=result["summary"],
        findings=result["findings"],
        changed_files=result["changed_files"],
        request_payload={**body.model_dump(), "analysis_context": analysis_context},
    )
    return _to_review_response(record)


@router.post("/fix", response_model=ReviewFixResponse)
async def generate_fix_endpoint(
    body: ReviewFixRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    record = get_review(supabase, review_id=body.review_id, user_id=user_id)

    # If DB record not found but the request carries enough inline data, allow
    # fix generation anyway (covers the case where the review was in-memory only
    # due to a stale schema-unavailable cache at creation time).
    if record is None and body.finding and body.repo_id:
        # Verify the user owns the repo passed inline
        _ensure_repo_access(supabase, user_id, body.repo_id)
        suggested_fix = await generate_fix_text({
            "review_id": body.review_id,
            "repo_id": body.repo_id,
            "finding": body.finding,
            "file": body.file,
            "code_area": body.code_area,
            "recommendation": body.recommendation,
        })
        return ReviewFixResponse(
            review_id=body.review_id,
            suggested_fix=suggested_fix,
            target_file=body.file,
            metadata={"finding_id": body.finding_id, "source": "inline"},
        )

    if not record:
        raise HTTPException(status_code=404, detail="Review not found")

    # Verify user has access to the repository owning this review
    _ensure_repo_access(supabase, user_id, record["repo_id"])

    target_finding = None
    findings = record.get("findings") or []
    if body.finding_id:
        target_finding = next((f for f in findings if f.get("id") == body.finding_id), None)
    if target_finding is None and body.finding:
        target_finding = {"finding": body.finding, "file": body.file, "code_area": body.code_area}
    if target_finding is None and findings:
        target_finding = findings[0]

    if target_finding is None:
        raise HTTPException(status_code=400, detail="No finding available for fix generation")

    suggested_fix = await generate_fix_text({
        "review_id": body.review_id,
        "repo_id": record.get("repo_id"),
        "finding": target_finding.get("finding"),
        "file": target_finding.get("file"),
        "code_area": target_finding.get("code_area"),
        "recommendation": target_finding.get("recommendation"),
    })

    return ReviewFixResponse(
        review_id=body.review_id,
        suggested_fix=suggested_fix,
        target_file=target_finding.get("file"),
        metadata={"finding_id": target_finding.get("id")},
    )


@router.get("", response_model=ReviewListResponse)
async def list_reviews_endpoint(
    repo_id: str = Query(..., description="Repository ID"),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    rows = list_reviews(supabase, repo_id=repo_id, user_id=user_id, limit=limit)
    items = [
        ReviewHistoryItem(
            review_id=row["id"],
            repo_id=row["repo_id"],
            target_type=_normalize_target_type(str(row.get("target_type") or "file")),
            status=row.get("status", "completed"),
            summary=row.get("summary") or "",
            commit_hash=row.get("commit_hash"),
            changed_files=row.get("changed_files") or [],
            analysis_context=row.get("analysis_context") or (row.get("request_payload") or {}).get("analysis_context") or {},
            created_at=row.get("created_at"),
        )
        for row in rows
    ]
    return ReviewListResponse(items=items)


@router.get("/{review_id}", response_model=ReviewRunResponse)
async def get_review_endpoint(
    review_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    row = get_review(supabase, review_id=review_id, user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    _ensure_repo_access(supabase, user_id, row["repo_id"])
    return _to_review_response(row)


@router.delete("/{review_id}")
async def delete_review_endpoint(
    review_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    row = get_review(supabase, review_id=review_id, user_id=user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    _ensure_repo_access(supabase, user_id, row["repo_id"])

    ok = delete_review(supabase, review_id=review_id, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete review")
    return {"message": "Review deleted"}

