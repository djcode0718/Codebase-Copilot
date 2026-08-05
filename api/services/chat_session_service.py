"""Chat session orchestration helpers."""

from __future__ import annotations

import asyncio
import re
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


_GENERIC_TITLES = {"new chat", "untitled", "conversation 1", "main workspace session", ""}
_TITLE_STOPWORDS = {
    "about", "above", "after", "again", "against", "with", "from", "that", "this", "there",
    "their", "what", "when", "where", "which", "would", "could", "should", "please", "explain",
    "tell", "show", "give", "codebase", "repository", "repo", "question", "questions",
}


def _normalize_title(raw: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]*", raw or "")
    cleaned = [w.strip(".-_") for w in words if w.strip(".-_")]
    if not cleaned:
        return "Repository Overview"

    title_words = []
    for word in cleaned:
        lower = word.lower()
        if lower in _TITLE_STOPWORDS and title_words:
            continue
        if lower in {"new", "chat", "untitled", "conversation"}:
            continue
        title_words.append(word[:32])
        if len(title_words) >= 5:
            break

    if not title_words:
        title_words = [w for w in cleaned if w.lower() not in {"new", "chat", "untitled", "conversation"}][:5]
    if not title_words:
        return "Repository Overview"

    title = " ".join(w[:1].upper() + w[1:] for w in title_words[:5])
    return "Repository Overview" if title.lower() in _GENERIC_TITLES else title


async def generate_conversation_title(prompts: list[str]) -> str:
    prompt_text = "\n".join(p.strip() for p in prompts if p and p.strip())[:1200]
    if not prompt_text:
        return "Repository Overview"

    llm_prompt = (
        "Create a concise repository chat title from these user prompts.\n"
        "Rules: max 5 words, Title Case, no punctuation, never use New Chat, Untitled, or Conversation 1.\n\n"
        f"Prompts:\n{prompt_text}\n\nTitle:"
    )
    try:
        from app.services.llm_fallback import generate_with_fallback

        generated = await asyncio.wait_for(generate_with_fallback(llm_prompt), timeout=4)
        title = _normalize_title((generated or "").split("\n", 1)[0])
        if title.lower() not in _GENERIC_TITLES:
            return title
    except Exception:
        pass

    return _normalize_title(prompt_text)


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
        payload["title"] = title.strip()[:180] if title.strip() else "Repository Overview"
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

