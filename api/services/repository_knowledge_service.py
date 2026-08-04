"""Repository-level memory retrieval from prior sessions and summaries."""

from __future__ import annotations

from typing import Dict, Any, List

from supabase import Client

from api.services.chat_history_service import get_repo_memory_messages, get_repo_conversation_summaries


def _score_text_match(query: str, text: str) -> int:
    terms = [t for t in query.lower().split() if len(t) >= 3]
    hay = (text or "").lower()
    if not terms or not hay:
        return 0
    return sum(1 for t in terms if t in hay)


def _summary_match_text(summary: Dict[str, Any]) -> str:
    return " ".join(
        [
            summary.get("title") or "",
            summary.get("executive_summary") or "",
            summary.get("technical_summary") or "",
            " ".join(summary.get("keywords") or []),
            " ".join(summary.get("tags") or []),
            " ".join(summary.get("files_discussed") or []),
            " ".join(summary.get("services_discussed") or []),
            " ".join(summary.get("modules_discussed") or []),
            " ".join(summary.get("classes_discussed") or []),
            " ".join(summary.get("apis_discussed") or []),
        ]
    )


def _message_anchor(message: Dict[str, Any], score: int) -> Dict[str, Any]:
    content = (message.get("content") or "").strip()
    return {
        "chat_id": message.get("chat_id"),
        "title": "Previous conversation",
        "executive_summary": content[:240],
        "technical_summary": "",
        "keywords": [],
        "tags": ["conversation-memory"],
        "files_discussed": [],
        "services_discussed": [],
        "modules_discussed": [],
        "classes_discussed": [],
        "apis_discussed": [],
        "anchor_type": "message",
        "anchor_score": score,
        "updated_at": message.get("created_at"),
    }


def get_repository_knowledge_context(
    supabase: Client,
    *,
    user_id: str,
    repo_id: str,
    query: str,
    chat_id: str,
    max_items: int = 3,
) -> List[Dict[str, Any]]:
    summaries = get_repo_conversation_summaries(supabase, repo_id=repo_id, user_id=user_id)
    ranked: List[Dict[str, Any]] = []
    seen_chat_ids = set()

    for summary in summaries:
        if summary.get("chat_id") == chat_id:
            continue
        text = _summary_match_text(summary)
        score = _score_text_match(query, text)
        if score <= 0:
            continue
        seen_chat_ids.add(summary.get("chat_id"))
        ranked.append(
            {
                "score": score,
                "summary": {
                    **summary,
                    "anchor_type": "summary",
                    "anchor_score": score,
                },
            }
        )

    # Backfill memory anchors using prior messages when no summary match exists.
    recent_messages = get_repo_memory_messages(
        supabase,
        repo_id,
        exclude_chat_id=chat_id,
        limit=max(12, max_items * 6),
    )
    for message in recent_messages:
        anchor_chat_id = message.get("chat_id")
        if not anchor_chat_id or anchor_chat_id in seen_chat_ids:
            continue
        msg_score = _score_text_match(query, message.get("content") or "")
        if msg_score <= 0:
            continue
        seen_chat_ids.add(anchor_chat_id)
        ranked.append({"score": msg_score, "summary": _message_anchor(message, msg_score)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return [entry["summary"] for entry in ranked[:max_items]]

