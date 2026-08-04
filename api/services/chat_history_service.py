"""Chat history retrieval helpers with repository/user guards."""

from __future__ import annotations

from typing import Dict, Any, List

from supabase import Client

from api.services import supabase_service


def get_chat_history(supabase: Client, chat_id: str) -> List[Dict[str, Any]]:
    return supabase_service.get_messages_for_chat(supabase, chat_id)


def get_repo_memory_messages(
    supabase: Client,
    repo_id: str,
    *,
    exclude_chat_id: str | None = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    return supabase_service.get_recent_messages_for_repo(
        supabase,
        repo_id,
        exclude_chat_id=exclude_chat_id,
        limit=limit,
    )

