"""Repository-level memory retrieval from prior sessions and summaries."""

from __future__ import annotations

from typing import Dict, Any, List

from supabase import Client

from api.services import supabase_service


def _score_text_match(query: str, text: str) -> int:
    terms = [t for t in query.lower().split() if len(t) >= 3]
    hay = (text or "").lower()
    if not terms or not hay:
        return 0
    return sum(1 for t in terms if t in hay)


def get_repository_knowledge_context(
    supabase: Client,
    *,
    user_id: str,
    repo_id: str,
    query: str,
    chat_id: str,
    max_items: int = 3,
) -> List[Dict[str, Any]]:
    summaries = supabase_service.get_conversation_summaries_for_repo(supabase, repo_id=repo_id, user_id=user_id)
    ranked: List[Dict[str, Any]] = []
    for summary in summaries:
        if summary.get("chat_id") == chat_id:
            continue
        text = " ".join(
            [
                summary.get("title") or "",
                summary.get("executive_summary") or "",
                summary.get("technical_summary") or "",
                " ".join(summary.get("keywords") or []),
                " ".join(summary.get("tags") or []),
            ]
        )
        score = _score_text_match(query, text)
        if score <= 0:
            continue
        ranked.append({"score": score, "summary": summary})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return [entry["summary"] for entry in ranked[:max_items]]

