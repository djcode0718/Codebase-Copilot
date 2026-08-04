"""Conversation search across titles, summaries, and message content."""

from __future__ import annotations

from typing import Dict, Any, List

from supabase import Client

from api.services import supabase_service


def _snippet(text: str, query: str, radius: int = 70) -> str:
    if not text:
        return ""
    idx = text.lower().find(query.lower())
    if idx < 0:
        return text[: radius * 2].strip()
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    return text[start:end].strip()


def search_repository_conversations(
    supabase: Client,
    *,
    user_id: str,
    repo_id: str,
    query: str,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    sessions = supabase_service.search_chats(supabase, user_id=user_id, repo_id=repo_id, query=query, limit=limit, offset=offset)
    results: List[Dict[str, Any]] = []
    for chat in sessions:
        chat_id = chat["id"]
        matched_messages = supabase_service.search_messages_in_chat(supabase, chat_id=chat_id, query=query, limit=5)
        snippets = []
        if chat.get("title"):
            snippets.append(_snippet(chat["title"], query))
        summary = supabase_service.get_conversation_summary(supabase, chat_id)
        if summary:
            snippets.append(_snippet(summary.get("executive_summary") or "", query))
            snippets.extend(_snippet(msg.get("content") or "", query) for msg in matched_messages[:2])
        else:
            snippets.extend(_snippet(msg.get("content") or "", query) for msg in matched_messages[:3])

        results.append(
            {
                "chat": chat,
                "matched_messages": matched_messages,
                "snippets": [s for s in snippets if s],
            }
        )
    return results

