"""
api/services/supabase_service.py
─────────────────────────────────
All Supabase database operations in one place.
Every router goes through these helpers — no raw Supabase calls in routers.

Tables used (see schema in blueprint):
  profiles, repositories, chats, messages, evaluations
"""

import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from supabase import Client
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Repositories ──────────────────────────────────────────────────────────────

def create_repo_record(
    supabase: Client,
    user_id: str,
    name: str,
    source_url: str,
    index_name: str,
    llm_provider: str,
) -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "name": name,
        "source_url": source_url,
        "index_name": index_name,
        "status": "indexing",
        "llm_provider": llm_provider,
    }
    result = supabase.table("repositories").insert(record).execute()
    return result.data[0] if result.data else record


def update_repo_status(
    supabase: Client,
    repo_id: str,
    status: str,
    file_count: Optional[int] = None,
    node_count: Optional[int] = None,
) -> None:
    update_data: Dict[str, Any] = {"status": status}
    if status == "ready":
        update_data["indexed_at"] = datetime.now(timezone.utc).isoformat()
    if file_count is not None:
        update_data["file_count"] = file_count
    if node_count is not None:
        update_data["node_count"] = node_count

    supabase.table("repositories").update(update_data).eq("id", repo_id).execute()


def reset_repo_for_reindex(supabase: Client, repo_id: str) -> None:
    """Prepare an existing repository record for a fresh indexing run."""
    supabase.table("repositories").update({
        "status": "indexing",
        "file_count": None,
        "node_count": None,
        "indexed_at": None,
    }).eq("id", repo_id).execute()


def get_repo(supabase: Client, repo_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = supabase.table("repositories").select("*").eq("id", repo_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"get_repo failed for id='{repo_id}': {e}")
        return None


def get_repos_for_user(supabase: Client, user_id: str) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("repositories")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning(f"get_repos_for_user failed for user_id='{user_id}': {e}")
        return []


def get_inflight_repo_for_source(
    supabase: Client,
    user_id: str,
    source_url: str,
) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("repositories")
            .select("*")
            .eq("user_id", user_id)
            .eq("source_url", source_url)
            .eq("status", "indexing")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(result, "data", None)
        if not isinstance(data, list) or not data:
            return None
        first = data[0]
        return first if isinstance(first, dict) else None
    except Exception as e:
        logger.warning(
            f"get_inflight_repo_for_source failed for user_id='{user_id}', source='{source_url}': {e}"
        )
        return None


def delete_repo(supabase: Client, repo_id: str) -> None:
    supabase.table("repositories").delete().eq("id", repo_id).execute()


# ── Chats ─────────────────────────────────────────────────────────────────────

def create_chat(
    supabase: Client,
    user_id: str,
    repo_id: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "repo_id": repo_id,
        "title": title,
    }
    result = supabase.table("chats").insert(record).execute()
    return result.data[0] if result.data else record


def get_chats_for_repo(supabase: Client, repo_id: str) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("chats")
            .select("*")
            .eq("repo_id", repo_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning(f"get_chats_for_repo failed for repo_id='{repo_id}': {e}")
        return []


def update_chat_title(supabase: Client, chat_id: str, title: str) -> None:
    supabase.table("chats").update({
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", chat_id).execute()


def delete_chat(supabase: Client, chat_id: str) -> None:
    supabase.table("chats").delete().eq("id", chat_id).execute()


def get_chat(supabase: Client, chat_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = supabase.table("chats").select("*").eq("id", chat_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"get_chat failed for id='{chat_id}': {e}")
        return None


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(
    supabase: Client,
    chat_id: str,
    role: str,
    content: str,
    query_mode: Optional[str] = None,
    retrieved_files: Optional[List[Dict[str, Any]]] = None,
    latency_ms: Optional[int] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "chat_id": chat_id,
        "role": role,
        "content": content,
    }
    if query_mode is not None:
        record["query_mode"] = query_mode
    if retrieved_files is not None:
        record["retrieved_files"] = retrieved_files
    if latency_ms is not None:
        record["latency_ms"] = latency_ms

    result = supabase.table("messages").insert(record).execute()
    return result.data[0] if result.data else record


def get_messages_for_chat(supabase: Client, chat_id: str) -> List[Dict[str, Any]]:
    result = (
        supabase.table("messages")
        .select("*")
        .eq("chat_id", chat_id)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


# ── Evaluations ───────────────────────────────────────────────────────────────

def save_evaluation(
    supabase: Client,
    repo_id: str,
    user_id: str,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "repo_id": repo_id,
        "user_id": user_id,
        "hit_rate":              summary.get("hit_rate", 0.0),
        "mrr":                   summary.get("mrr", 0.0),
        "avg_faithfulness":      summary.get("avg_faithfulness", 0.0),
        "avg_relevancy":         summary.get("avg_relevancy", 0.0),
        "mode_accuracy":         summary.get("mode_accuracy", 0.0),
        "avg_latency_total":     summary.get("avg_latency_total", 0.0),
        "avg_latency_retrieval": summary.get("avg_latency_retrieval", 0.0),
        "avg_latency_rerank":    summary.get("avg_latency_rerank", 0.0),
        "avg_latency_llm":       summary.get("avg_latency_llm", 0.0),
        "colbert_enabled":       summary.get("colbert_enabled", False),
        "result_json":           summary,
    }
    result = supabase.table("evaluations").insert(record).execute()
    return result.data[0] if result.data else record


def get_latest_evaluation(
    supabase: Client, repo_id: str
) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("evaluations")
            .select("*")
            .eq("repo_id", repo_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"get_latest_evaluation failed for repo_id='{repo_id}': {e}")
        return None
