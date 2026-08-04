"""Repository memory orchestration for conversation intelligence."""

from __future__ import annotations

from typing import Dict, Any

from supabase import Client

from api.services import supabase_service
from api.services.conversation_summary_service import build_conversation_summary


def refresh_session_memory(supabase: Client, *, chat: Dict[str, Any]) -> Dict[str, Any]:
    chat_id = chat["id"]
    repo_id = chat["repo_id"]
    user_id = chat["user_id"]

    messages = supabase_service.get_messages_for_chat(supabase, chat_id)
    summary = build_conversation_summary(messages)

    # Keep chat card metadata fresh for faster UI listing and search.
    if not chat.get("title"):
        first_user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        if first_user:
            supabase_service.update_chat_fields(
                supabase,
                chat_id,
                {"title": first_user[:72] + ("..." if len(first_user) > 72 else "")},
            )

    supabase_service.upsert_conversation_summary(
        supabase,
        chat_id=chat_id,
        repo_id=repo_id,
        user_id=user_id,
        payload={"title": chat.get("title"), **summary},
    )
    supabase_service.replace_conversation_tags(supabase, chat_id=chat_id, tags=summary.get("tags") or [])
    return summary

