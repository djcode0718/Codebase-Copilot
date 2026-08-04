"""Chat session orchestration helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, Optional

from supabase import Client

from api.services import supabase_service


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_quick_ask_session(supabase: Client, user_id: str, repo_id: str) -> Dict[str, Any]:
    return supabase_service.create_chat(
        supabase,
        user_id=user_id,
        repo_id=repo_id,
        session_type="quick_ask",
    )


def get_or_create_main_session(supabase: Client, user_id: str, repo_id: str) -> Dict[str, Any]:
    existing = supabase_service.get_main_chat_for_repo(supabase, user_id=user_id, repo_id=repo_id)
    if existing:
        return existing
    return supabase_service.create_chat(
        supabase,
        user_id=user_id,
        repo_id=repo_id,
        title="Main Workspace Session",
        session_type="main",
    )


def update_session_flags(
    supabase: Client,
    chat_id: str,
    *,
    title: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    is_favorite: Optional[bool] = None,
    is_archived: Optional[bool] = None,
) -> None:
    payload: Dict[str, Any] = {"updated_at": _now_iso()}
    if title is not None:
        payload["title"] = title.strip()[:180] if title.strip() else "Untitled conversation"
    if is_pinned is not None:
        payload["is_pinned"] = bool(is_pinned)
    if is_favorite is not None:
        payload["is_favorite"] = bool(is_favorite)
    if is_archived is not None:
        payload["is_archived"] = bool(is_archived)
        payload["archived_at"] = _now_iso() if is_archived else None

    supabase_service.update_chat_fields(supabase, chat_id, payload)


def soft_delete_session(supabase: Client, chat_id: str) -> None:
    supabase_service.update_chat_fields(
        supabase,
        chat_id,
        {
            "deleted_at": _now_iso(),
            "updated_at": _now_iso(),
        },
    )


def restore_session(supabase: Client, chat_id: str) -> None:
    supabase_service.update_chat_fields(
        supabase,
        chat_id,
        {
            "deleted_at": None,
            "is_archived": False,
            "archived_at": None,
            "updated_at": _now_iso(),
        },
    )

