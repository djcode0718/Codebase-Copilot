"""Persistence facade for engineering review records.

Delegates all storage operations to supabase_service, providing a focused
interface that callers can import without depending on the full Supabase
service module directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from supabase import Client

from api.services import supabase_service


def store_review(supabase: Client, **kwargs: Any) -> Dict[str, Any]:
    """Persist a new engineering review record.

    Accepts the same keyword arguments as
    ``supabase_service.insert_repository_review``:
        repo_id, user_id, target_type, summary, findings, changed_files,
        commit_hash, status, request_payload.
    """
    return supabase_service.insert_repository_review(supabase, **kwargs)


def list_reviews(supabase: Client, *, repo_id: str, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    return supabase_service.list_repository_reviews(supabase, repo_id=repo_id, user_id=user_id, limit=limit)


def get_review(supabase: Client, *, review_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return supabase_service.get_repository_review_by_id(supabase, review_id=review_id, user_id=user_id)


def delete_review(supabase: Client, *, review_id: str, user_id: str) -> bool:
    return supabase_service.delete_repository_review(supabase, review_id=review_id, user_id=user_id)
