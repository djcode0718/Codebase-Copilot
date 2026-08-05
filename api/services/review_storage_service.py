"""Persistence facade for engineering review records."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from supabase import Client

from api.services import supabase_service


def store_review(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    target_type: str,
    summary: str,
    findings: List[Dict[str, Any]],
    changed_files: List[str],
    commit_hash: Optional[str] = None,
    status: str = "completed",
    request_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return supabase_service.insert_repository_review(
        supabase,
        repo_id=repo_id,
        user_id=user_id,
        target_type=target_type,
        summary=summary,
        findings=findings,
        changed_files=changed_files,
        commit_hash=commit_hash,
        status=status,
        request_payload=request_payload or {},
    )


def list_reviews(supabase: Client, *, repo_id: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    return supabase_service.list_repository_reviews(supabase, repo_id=repo_id, user_id=user_id, limit=limit)


def get_review(supabase: Client, *, review_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return supabase_service.get_repository_review_by_id(supabase, review_id=review_id, user_id=user_id)


def delete_review(supabase: Client, *, review_id: str, user_id: str) -> bool:
    return supabase_service.delete_repository_review(supabase, review_id=review_id, user_id=user_id)

