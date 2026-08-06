"""
api/services/supabase_service.py
─────────────────────────────────
All Supabase database operations in one place.
Every router goes through these helpers — no raw Supabase calls in routers.

Tables used (see schema in blueprint):
  profiles, repositories, chats, messages, evaluations
"""

import uuid
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timezone, timedelta

from supabase import Client
from app.utils.logger import get_logger

logger = get_logger(__name__)
_HEALTH_SCHEMA_CHECK_TTL_SECONDS = 60
_REVIEW_SCHEMA_CHECK_TTL_SECONDS = 60
_MISSING_REPO_MEMORY_TABLE_WARNED: Set[str] = set()


def _is_missing_column_error(err: Exception, columns: List[str]) -> bool:
    """Detect PostgREST/Supabase missing-column errors for older schemas."""
    msg = str(err)
    lowered = msg.lower()
    if "column" not in lowered:
        return False
    return any(col.lower() in lowered for col in columns)


def _is_missing_health_table_error(err: Exception) -> bool:
    msg = str(err).lower()
    if "pgrst205" in msg and "repository_health_" in msg:
        return True
    return "could not find the table 'public.repository_health_" in msg


def _is_missing_review_table_error(err: Exception) -> bool:
    msg = str(err).lower()
    if "pgrst205" in msg and "repository_reviews" in msg:
        return True
    return "could not find the table 'public.repository_reviews'" in msg


def _missing_repo_memory_table_name(err: Exception) -> Optional[str]:
    msg = str(err).lower()
    for table in ("conversation_summaries", "conversation_tags"):
        if table in msg and ("could not find the table" in msg or "schema cache" in msg or "pgrst205" in msg):
            return table
    return None


def _warn_missing_repo_memory_table_once(table_name: str) -> None:
    if table_name in _MISSING_REPO_MEMORY_TABLE_WARNED:
        return
    logger.warning(
        f"Repository memory table '{table_name}' is missing. Apply repository memory migration to enable this feature."
    )
    _MISSING_REPO_MEMORY_TABLE_WARNED.add(table_name)


class _SchemaAvailabilityChecker:
    """Reusable cached schema availability check to eliminate duplicate logic."""

    def __init__(
        self,
        table_name: str,
        missing_error_detector: Any,
        ttl_seconds: int,
        warning_message: str,
    ) -> None:
        self._table_name = table_name
        self._missing_error_detector = missing_error_detector
        self._ttl_seconds = ttl_seconds
        self._warning_message = warning_message
        self._available: Optional[bool] = None
        self._last_checked_at: Optional[datetime] = None
        self._warned = False

    def is_available(self, supabase: Client, *, force_refresh: bool = False) -> bool:
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and self._last_checked_at is not None
            and (now - self._last_checked_at).total_seconds() < self._ttl_seconds
            and self._available is not None
        ):
            return bool(self._available)

        try:
            supabase.table(self._table_name).select("id").limit(1).execute()
            self._available = True
            self._last_checked_at = now
            return True
        except Exception as e:
            self._available = False
            self._last_checked_at = now
            if self._missing_error_detector(e):
                if not self._warned:
                    logger.warning(self._warning_message)
                    self._warned = True
                return False
            logger.warning(f"{self._table_name} schema availability check failed: {e}")
            return False


_health_checker = _SchemaAvailabilityChecker(
    table_name="repository_health_runs",
    missing_error_detector=_is_missing_health_table_error,
    ttl_seconds=_HEALTH_SCHEMA_CHECK_TTL_SECONDS,
    warning_message="Repository health schema is missing. Apply migration before enabling persisted health runs.",
)

_review_checker = _SchemaAvailabilityChecker(
    table_name="repository_reviews",
    missing_error_detector=_is_missing_review_table_error,
    ttl_seconds=_REVIEW_SCHEMA_CHECK_TTL_SECONDS,
    warning_message="Repository review schema is missing. Apply migration before enabling persisted review runs.",
)


def is_repository_health_schema_available(
    supabase: Client, *, force_refresh: bool = False,
) -> bool:
    return _health_checker.is_available(supabase, force_refresh=force_refresh)


def is_repository_review_schema_available(
    supabase: Client, *, force_refresh: bool = False,
) -> bool:
    return _review_checker.is_available(supabase, force_refresh=force_refresh)


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


def update_repo_llm_provider(supabase: Client, repo_id: str, llm_provider: str) -> None:
    """Persist the most recently used runtime LLM provider/model label."""
    value = (llm_provider or "").strip()
    if not value:
        return
    supabase.table("repositories").update({"llm_provider": value}).eq("id", repo_id).execute()


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
    session_type: str = "quick_ask",
) -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "repo_id": repo_id,
        "title": title,
        "session_type": session_type,
        "is_pinned": False,
        "is_favorite": False,
        "is_archived": False,
        "deleted_at": None,
        "last_message_at": None,
        "last_message_preview": None,
        "message_count": 0,
    }
    try:
        result = supabase.table("chats").insert(record).execute()
        return result.data[0] if result.data else record
    except Exception as e:
        if not _is_missing_column_error(
            e,
            [
                "session_type",
                "is_pinned",
                "is_favorite",
                "is_archived",
                "deleted_at",
                "archived_at",
                "last_message_at",
                "last_message_preview",
                "message_count",
            ],
        ):
            raise
        # Chats schema graceful fallback: keep only stable columns.
        legacy_record = {
            "id": record["id"],
            "user_id": user_id,
            "repo_id": repo_id,
            "title": title,
        }
        legacy_result = supabase.table("chats").insert(legacy_record).execute()
        return legacy_result.data[0] if legacy_result.data else legacy_record


def get_chats_for_repo(
    supabase: Client,
    repo_id: str,
    *,
    include_archived: bool = True,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    try:
        query = (
            supabase.table("chats")
            .select("*")
            .eq("repo_id", repo_id)
        )
        if not include_archived:
            query = query.eq("is_archived", False)
        if not include_deleted:
            query = query.is_("deleted_at", "null")
        result = query.order("is_pinned", desc=True).order("updated_at", desc=True).range(offset, offset + max(1, limit) - 1).execute()
        data = getattr(result, "data", None)
        if isinstance(data, list):
            return data

        # Simplified fallback for minimal/mocked adapters without .is_/.range.
        fallback = (
            supabase.table("chats")
            .select("*")
            .eq("repo_id", repo_id)
            .order("updated_at", desc=True)
            .execute()
        )
        fallback_data = getattr(fallback, "data", None)
        return fallback_data if isinstance(fallback_data, list) else []
    except Exception as e:
        if _is_missing_column_error(e, ["deleted_at", "is_pinned", "is_archived"]):
            try:
                fallback = (
                    supabase.table("chats")
                    .select("*")
                    .eq("repo_id", repo_id)
                    .order("updated_at", desc=True)
                    .execute()
                )
                data = getattr(fallback, "data", None)
                return data if isinstance(data, list) else []
            except Exception as fallback_err:
                logger.warning(
                    f"get_chats_for_repo legacy fallback failed for repo_id='{repo_id}': {fallback_err}"
                )
                return []
        logger.warning(f"get_chats_for_repo failed for repo_id='{repo_id}': {e}")
        return []


def update_chat_title(supabase: Client, chat_id: str, title: str) -> None:
    supabase.table("chats").update({
        "title": title,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", chat_id).execute()


def update_chat_fields(supabase: Client, chat_id: str, fields: Dict[str, Any]) -> None:
    payload = dict(fields)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        supabase.table("chats").update(payload).eq("id", chat_id).execute()
    except Exception as e:
        if not _is_missing_column_error(
            e,
            ["session_type", "is_pinned", "is_favorite", "is_archived", "deleted_at", "archived_at"],
        ):
            raise
        allowed = {k: v for k, v in payload.items() if k in {"title", "updated_at"}}
        if not allowed:
            return
        supabase.table("chats").update(allowed).eq("id", chat_id).execute()


def delete_chat(supabase: Client, chat_id: str) -> None:
    """Hard delete chat and all associated messages."""
    # Delete all messages for this chat first
    try:
        supabase.table("messages").delete().eq("chat_id", chat_id).execute()
    except Exception as e:
        logger.warning(f"Failed to delete messages for chat {chat_id}: {e}")
    
    # Then delete the chat itself
    supabase.table("chats").delete().eq("id", chat_id).execute()


def get_chat(supabase: Client, chat_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = supabase.table("chats").select("*").eq("id", chat_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.warning(f"get_chat failed for id='{chat_id}': {e}")
        return None


def get_main_chat_for_repo(supabase: Client, user_id: str, repo_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("chats")
            .select("*")
            .eq("user_id", user_id)
            .eq("repo_id", repo_id)
            .eq("session_type", "main")
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        if _is_missing_column_error(e, ["session_type", "deleted_at"]):
            # Older schema fallback: infer main session by canonical title.
            try:
                fallback = (
                    supabase.table("chats")
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("repo_id", repo_id)
                    .eq("title", "Main Workspace Session")
                    .limit(1)
                    .execute()
                )
                return fallback.data[0] if fallback.data else None
            except Exception as fallback_err:
                logger.warning(
                    f"get_main_chat_for_repo fallback failed for repo_id='{repo_id}': {fallback_err}"
                )
                return None
        logger.warning(f"get_main_chat_for_repo failed for repo_id='{repo_id}': {e}")
        return None


def delete_all_chats_for_repo(supabase: Client, repo_id: str, user_id: str) -> None:
    payload = {
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        supabase.table("chats").update(payload).eq("repo_id", repo_id).eq("user_id", user_id).execute()
    except Exception as e:
        if not _is_missing_column_error(e, ["deleted_at"]):
            raise
        supabase.table("chats").delete().eq("repo_id", repo_id).eq("user_id", user_id).execute()


def soft_delete_chats(supabase: Client, *, chat_ids: List[str], user_id: str, repo_id: Optional[str] = None) -> int:
    ids = [cid for cid in chat_ids if cid]
    if not ids:
        return 0

    payload = {
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    query = supabase.table("chats").update(payload).eq("user_id", user_id).in_("id", ids)
    if repo_id:
        query = query.eq("repo_id", repo_id)
    result = query.execute()
    data = getattr(result, "data", None)
    return len(data) if isinstance(data, list) else len(ids)


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(
    supabase: Client,
    chat_id: str,
    role: str,
    content: str,
    query_mode: Optional[str] = None,
    retrieved_files: Optional[List[Dict[str, Any]]] = None,
    latency_ms: Optional[int] = None,
    token_count: Optional[int] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    next_sequence = _next_message_sequence(supabase, chat_id)
    record: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "sequence": next_sequence,
    }
    if query_mode is not None:
        record["query_mode"] = query_mode
    if retrieved_files is not None:
        record["retrieved_files"] = retrieved_files
    if latency_ms is not None:
        record["latency_ms"] = latency_ms
    if token_count is not None:
        record["token_count"] = token_count
    if llm_provider is not None:
        record["llm_provider"] = llm_provider
    if llm_model is not None:
        record["llm_model"] = llm_model
    if metadata:
        record["metadata"] = metadata

    try:
        result = supabase.table("messages").insert(record).execute()
    except Exception as e:
        if not _is_missing_column_error(e, ["token_count", "llm_provider", "llm_model", "metadata", "sequence"]):
            raise
        legacy_record = {k: v for k, v in record.items() if k in {"id", "chat_id", "role", "content", "query_mode", "retrieved_files", "latency_ms"}}
        result = supabase.table("messages").insert(legacy_record).execute()
        record = legacy_record

    saved = result.data[0] if result.data else record
    _touch_chat_after_message(supabase, chat_id, saved)
    return saved


def _next_message_sequence(supabase: Client, chat_id: str) -> int:
    try:
        result = (
            supabase.table("messages")
            .select("sequence")
            .eq("chat_id", chat_id)
            .order("sequence", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        current = rows[0].get("sequence") if rows else None
        return int(current or 0) + 1
    except Exception:
        return 1


def _touch_chat_after_message(supabase: Client, chat_id: str, message: Dict[str, Any]) -> None:
    now = message.get("created_at") or datetime.now(timezone.utc).isoformat()
    preview = (message.get("content") or "").strip().replace("\n", " ")[:240]
    payload: Dict[str, Any] = {
        "updated_at": now,
        "last_message_at": now,
        "last_message_preview": preview,
    }
    try:
        payload["message_count"] = count_messages_for_chat(supabase, chat_id)
        supabase.table("chats").update(payload).eq("id", chat_id).execute()
    except Exception as e:
        if not _is_missing_column_error(e, ["last_message_at", "last_message_preview", "message_count"]):
            logger.warning(f"Failed to update chat message metadata for chat_id='{chat_id}': {e}")
        try:
            supabase.table("chats").update({"updated_at": now}).eq("id", chat_id).execute()
        except Exception:
            pass


def count_messages_for_chat(supabase: Client, chat_id: str) -> int:
    try:
        result = supabase.table("messages").select("id").eq("chat_id", chat_id).execute()
        data = getattr(result, "data", None)
        if isinstance(data, list):
            return len(data)
    except Exception:
        pass
    try:
        return len(get_messages_for_chat(supabase, chat_id))
    except Exception:
        return 0


def get_messages_for_chat(
    supabase: Client,
    chat_id: str,
    *,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    try:
        query = (
            supabase.table("messages")
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
        )
        if limit is not None:
            query = query.range(offset, offset + max(1, limit) - 1)
        result = query.execute()
        return result.data or []
    except Exception as e:
        if not _is_missing_column_error(e, ["sequence"]):
            raise
        query = (
            supabase.table("messages")
            .select("*")
            .eq("chat_id", chat_id)
            .order("created_at", desc=False)
        )
        if limit is not None:
            query = query.range(offset, offset + max(1, limit) - 1)
        result = query.execute()
        return result.data or []


def get_recent_messages_for_repo(
    supabase: Client,
    repo_id: str,
    *,
    exclude_chat_id: Optional[str] = None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    try:
        chats = get_chats_for_repo(
            supabase,
            repo_id,
            include_archived=True,
            include_deleted=False,
            limit=max(limit, 10),
            offset=0,
        )
        chat_ids = [c["id"] for c in chats if c.get("id") and c.get("id") != exclude_chat_id]
        if not chat_ids:
            return []

        result = (
            supabase.table("messages")
            .select("*")
            .in_("chat_id", chat_ids)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        data = result.data or []
        return list(reversed(data))
    except Exception as e:
        logger.warning(f"get_recent_messages_for_repo failed for repo_id='{repo_id}': {e}")
        return []


def search_chats(
    supabase: Client,
    *,
    user_id: str,
    repo_id: str,
    query: str,
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("chats")
            .select("*")
            .eq("user_id", user_id)
            .eq("repo_id", repo_id)
            .is_("deleted_at", "null")
            .or_(f"title.ilike.%{query}%,summary.ilike.%{query}%")
            .order("is_pinned", desc=True)
            .order("updated_at", desc=True)
            .range(offset, offset + max(1, limit) - 1)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning(f"search_chats fallback scan for repo_id='{repo_id}': {e}")
        # Fallback when ilike/or is unavailable in mocked tests or local adapters.
        all_chats = get_chats_for_repo(supabase, repo_id, include_archived=True, include_deleted=False, limit=300, offset=0)
        q = query.lower()
        matches = [
            c for c in all_chats
            if q in (c.get("title") or "").lower() or q in (c.get("summary") or "").lower()
        ]
        return matches[offset: offset + max(1, limit)]


def search_messages_in_chat(
    supabase: Client,
    *,
    chat_id: str,
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("messages")
            .select("*")
            .eq("chat_id", chat_id)
            .ilike("content", f"%{query}%")
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception:
        messages = get_messages_for_chat(supabase, chat_id)
        q = query.lower()
        return [m for m in messages if q in (m.get("content") or "").lower()][:limit]


def upsert_conversation_summary(
    supabase: Client,
    *,
    chat_id: str,
    repo_id: str,
    user_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    record = {
        "chat_id": chat_id,
        "repo_id": repo_id,
        "user_id": user_id,
        **payload,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        existing = get_conversation_summary(supabase, chat_id)
        if existing and existing.get("id"):
            result = supabase.table("conversation_summaries").update(record).eq("id", existing["id"]).execute()
        else:
            record["id"] = str(uuid.uuid4())
            result = supabase.table("conversation_summaries").insert(record).execute()
        return result.data[0] if result.data else record
    except Exception as e:
        missing_table = _missing_repo_memory_table_name(e)
        if missing_table:
            _warn_missing_repo_memory_table_once(missing_table)
        else:
            logger.warning(f"upsert_conversation_summary skipped for chat_id='{chat_id}': {e}")
        return record


def get_conversation_summary(supabase: Client, chat_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("conversation_summaries")
            .select("*")
            .eq("chat_id", chat_id)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception:
        return None


def get_conversation_summaries_for_repo(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("conversation_summaries")
            .select("*")
            .eq("repo_id", repo_id)
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        missing_table = _missing_repo_memory_table_name(e)
        if missing_table:
            _warn_missing_repo_memory_table_once(missing_table)
            return []
        logger.warning(f"get_conversation_summaries_for_repo failed for repo_id='{repo_id}': {e}")
        return []


def replace_conversation_tags(supabase: Client, *, chat_id: str, tags: List[str]) -> None:
    try:
        supabase.table("conversation_tags").delete().eq("chat_id", chat_id).execute()
        rows = [
            {
                "id": str(uuid.uuid4()),
                "chat_id": chat_id,
                "tag": tag,
            }
            for tag in tags
            if tag.strip()
        ]
        if rows:
            supabase.table("conversation_tags").insert(rows).execute()
    except Exception as e:
        missing_table = _missing_repo_memory_table_name(e)
        if missing_table:
            _warn_missing_repo_memory_table_once(missing_table)
            return
        logger.warning(f"replace_conversation_tags failed for chat_id='{chat_id}': {e}")


def get_tags_for_chat(supabase: Client, chat_id: str) -> List[str]:
    try:
        result = supabase.table("conversation_tags").select("tag").eq("chat_id", chat_id).execute()
        return [row.get("tag") for row in (result.data or []) if row.get("tag")]
    except Exception:
        return []


# ── Attachments ───────────────────────────────────────────────────────────────

def create_attachment(
    supabase: Client,
    *,
    chat_id: str,
    user_id: str,
    filename: str,
    storage_path: str,
    mime_type: Optional[str] = None,
    file_size: Optional[int] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "chat_id": chat_id,
        "user_id": user_id,
        "filename": filename,
        "storage_path": storage_path,
    }
    if mime_type is not None:
        record["mime_type"] = mime_type
    if file_size is not None:
        record["file_size"] = file_size

    result = supabase.table("attachments").insert(record).execute()
    return result.data[0] if result.data else record


def get_attachments_for_chat(
    supabase: Client,
    *,
    chat_id: str,
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    query = supabase.table("attachments").select("*").eq("chat_id", chat_id)
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    result = query.order("created_at", desc=False).execute()
    data = getattr(result, "data", None)
    return data if isinstance(data, list) else []


def get_attachment(supabase: Client, attachment_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = supabase.table("attachments").select("*").eq("id", attachment_id).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_attachment(supabase: Client, attachment_id: str, fields: Dict[str, Any]) -> None:
    supabase.table("attachments").update(fields).eq("id", attachment_id).execute()


def soft_delete_attachment(supabase: Client, attachment_id: str) -> None:
    supabase.table("attachments").update({
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", attachment_id).execute()


# ── Saved Reports ─────────────────────────────────────────────────────────────

def create_saved_report(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    report_type: str,
    title: Optional[str],
    content: Dict[str, Any],
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "repo_id": repo_id,
        "user_id": user_id,
        "report_type": report_type,
        "title": title,
        "content": content,
    }
    result = supabase.table("saved_reports").insert(record).execute()
    return result.data[0] if result.data else record


def get_saved_reports_for_repo(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    query = supabase.table("saved_reports").select("*").eq("repo_id", repo_id).eq("user_id", user_id)
    if not include_deleted:
        query = query.is_("deleted_at", "null")
    result = query.order("updated_at", desc=True).execute()
    data = getattr(result, "data", None)
    return data if isinstance(data, list) else []


def get_saved_report(supabase: Client, report_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = supabase.table("saved_reports").select("*").eq("id", report_id).execute()
        return result.data[0] if result.data else None
    except Exception:
        return None


def update_saved_report(supabase: Client, report_id: str, fields: Dict[str, Any]) -> None:
    payload = dict(fields)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("saved_reports").update(payload).eq("id", report_id).execute()


def soft_delete_saved_report(supabase: Client, report_id: str) -> None:
    supabase.table("saved_reports").update({
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", report_id).execute()


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


def get_recent_evaluations(
    supabase: Client,
    *,
    repo_id: str,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase.table("evaluations")
            .select("*")
            .eq("repo_id", repo_id)
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 200)))
            .execute()
        )
        data = getattr(result, "data", None)
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.warning(f"get_recent_evaluations failed for repo_id='{repo_id}': {e}")
        return []


def get_evaluation_by_id(
    supabase: Client,
    *,
    repo_id: str,
    evaluation_id: str,
) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase.table("evaluations")
            .select("*")
            .eq("repo_id", repo_id)
            .eq("id", evaluation_id)
            .limit(1)
            .execute()
        )
        data = getattr(result, "data", None)
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception as e:
        logger.warning(
            f"get_evaluation_by_id failed for repo_id='{repo_id}', eval_id='{evaluation_id}': {e}"
        )
        return None


# -- Repository Health Intelligence -------------------------------------------

def insert_health_run(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    top_level: Dict[str, Any],
    executive_summary: str,
    strengths: List[str],
    weaknesses: List[str],
    critical_risks: List[str],
    architecture_risks: List[str],
    security_risks: List[str],
    performance_risks: List[str],
    recommended_sprint: List[str],
    improved_categories: List[str],
    declining_categories: List[str],
    new_risks: List[str],
    resolved_risks: List[str],
    benchmark: Dict[str, Any],
) -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "repo_id": repo_id,
        "user_id": user_id,
        "repository_health": int(top_level.get("repository_health", 0)),
        "grade": top_level.get("grade", "F"),
        "status": top_level.get("status", "At Risk"),
        "trend": int(top_level.get("trend", 0)),
        "repository_size": top_level.get("repository_size", "Small"),
        "language_detection": top_level.get("language_detection", []),
        "framework_detection": top_level.get("framework_detection", []),
        "executive_summary": executive_summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "critical_risks": critical_risks,
        "architecture_risks": architecture_risks,
        "security_risks": security_risks,
        "performance_risks": performance_risks,
        "recommended_sprint": recommended_sprint,
        "improved_categories": improved_categories,
        "declining_categories": declining_categories,
        "new_risks": new_risks,
        "resolved_risks": resolved_risks,
        "benchmark": benchmark,
    }
    result = supabase.table("repository_health_runs").insert(record).execute()
    return result.data[0] if result.data else record


def insert_health_category_scores(
    supabase: Client,
    *,
    run_id: str,
    repo_id: str,
    user_id: str,
    categories: List[Dict[str, Any]],
) -> None:
    rows = []
    for c in categories:
        rows.append({
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "repo_id": repo_id,
            "user_id": user_id,
            "category": c.get("category"),
            "score": int(c.get("score", 0)),
            "grade": c.get("grade", "F"),
            "trend": int(c.get("trend", 0)),
            "explanation": c.get("explanation", ""),
            "detected_problems": c.get("detected_problems", []),
            "positive_findings": c.get("positive_findings", []),
            "recommendations": c.get("recommendations", []),
            "affected_files": c.get("affected_files", []),
            "affected_modules": c.get("affected_modules", []),
        })
    if rows:
        supabase.table("repository_health_category_scores").insert(rows).execute()


def insert_health_findings(
    supabase: Client,
    *,
    run_id: str,
    repo_id: str,
    user_id: str,
    findings: List[Dict[str, Any]],
) -> None:
    rows = []
    for f in findings:
        rows.append({
            "id": f.get("id") or str(uuid.uuid4()),
            "run_id": run_id,
            "repo_id": repo_id,
            "user_id": user_id,
            "category": f.get("category"),
            "finding_type": f.get("finding_type"),
            "severity": f.get("severity", "low"),
            "title": f.get("title", ""),
            "details": f.get("details", ""),
            "evidence": f.get("evidence", {}),
            "recommendation": f.get("recommendation"),
            "affected_files": f.get("affected_files", []),
            "affected_modules": f.get("affected_modules", []),
            "expected_score_gain": int(f.get("expected_score_gain", 0)),
        })
    if rows:
        supabase.table("repository_health_findings").insert(rows).execute()


def insert_health_recommendations(
    supabase: Client,
    *,
    run_id: str,
    repo_id: str,
    user_id: str,
    recommendations: List[Dict[str, Any]],
) -> None:
    rows = []
    for r in recommendations:
        rows.append({
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "repo_id": repo_id,
            "user_id": user_id,
            "priority_rank": int(r.get("rank", 0)),
            "category": r.get("category"),
            "title": r.get("title", ""),
            "description": r.get("description", ""),
            "estimated_effort": r.get("estimated_effort", ""),
            "expected_score_gain": int(r.get("expected_score_gain", 0)),
            "impact_score": float(r.get("impact_score", 0.0)),
            "action_items": r.get("action_items", []),
            "affected_files": r.get("affected_files", []),
        })
    if rows:
        supabase.table("repository_health_recommendations").insert(rows).execute()


def get_latest_health_run(supabase: Client, *, repo_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return None
    try:
        result = (
            supabase.table("repository_health_runs")
            .select("*")
            .eq("repo_id", repo_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        if _is_missing_health_table_error(e):
            return None
        logger.warning(f"get_latest_health_run failed for repo_id='{repo_id}': {e}")
        return None


def get_health_run_by_id(supabase: Client, *, run_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return None
    try:
        result = (
            supabase.table("repository_health_runs")
            .select("*")
            .eq("id", run_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        if _is_missing_health_table_error(e):
            return None
        logger.warning(f"get_health_run_by_id failed for run_id='{run_id}': {e}")
        return None


def get_health_category_scores(supabase: Client, *, run_id: str, user_id: str) -> List[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return []
    try:
        result = (
            supabase.table("repository_health_category_scores")
            .select("*")
            .eq("run_id", run_id)
            .eq("user_id", user_id)
            .order("score", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as e:
        if _is_missing_health_table_error(e):
            return []
        logger.warning(f"get_health_category_scores failed for run_id='{run_id}': {e}")
        return []


def get_health_category_score_map(supabase: Client, *, run_id: str, user_id: str) -> Dict[str, int]:
    rows = get_health_category_scores(supabase, run_id=run_id, user_id=user_id)
    return {str(r.get("category")): int(r.get("score", 0)) for r in rows if r.get("category")}


def get_health_category_score(
    supabase: Client,
    *,
    run_id: str,
    user_id: str,
    category: str,
) -> Optional[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return None
    try:
        result = (
            supabase.table("repository_health_category_scores")
            .select("*")
            .eq("run_id", run_id)
            .eq("user_id", user_id)
            .eq("category", category)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        if _is_missing_health_table_error(e):
            return None
        logger.warning(f"get_health_category_score failed for run_id='{run_id}', category='{category}': {e}")
        return None


def get_health_findings(
    supabase: Client,
    *,
    run_id: str,
    user_id: str,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return []
    try:
        query = (
            supabase.table("repository_health_findings")
            .select("*")
            .eq("run_id", run_id)
            .eq("user_id", user_id)
        )
        if category:
            query = query.eq("category", category)
        result = query.order("created_at", desc=False).execute()
        return result.data or []
    except Exception as e:
        if _is_missing_health_table_error(e):
            return []
        logger.warning(f"get_health_findings failed for run_id='{run_id}': {e}")
        return []


def get_health_problem_titles(supabase: Client, *, run_id: str, user_id: str) -> List[str]:
    findings = get_health_findings(supabase, run_id=run_id, user_id=user_id)
    return [
        str(f.get("title"))
        for f in findings
        if f.get("finding_type") == "problem" and f.get("title")
    ]


def get_health_recommendations(supabase: Client, *, run_id: str, user_id: str) -> List[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return []
    try:
        result = (
            supabase.table("repository_health_recommendations")
            .select("*")
            .eq("run_id", run_id)
            .eq("user_id", user_id)
            .order("priority_rank", desc=False)
            .execute()
        )
        rows = result.data or []
        normalized = []
        for row in rows:
            normalized.append({
                "rank": row.get("priority_rank", 0),
                "title": row.get("title", ""),
                "description": row.get("description", ""),
                "category": row.get("category"),
                "estimated_effort": row.get("estimated_effort", ""),
                "expected_score_gain": row.get("expected_score_gain", 0),
                "impact_score": row.get("impact_score", 0.0),
                "action_items": row.get("action_items", []),
                "affected_files": row.get("affected_files", []),
            })
        return normalized
    except Exception as e:
        if _is_missing_health_table_error(e):
            return []
        logger.warning(f"get_health_recommendations failed for run_id='{run_id}': {e}")
        return []


def get_health_history(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    days: int = 30,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    if not is_repository_health_schema_available(supabase):
        return []
    try:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        result = (
            supabase.table("repository_health_runs")
            .select("*")
            .eq("repo_id", repo_id)
            .eq("user_id", user_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        if _is_missing_health_table_error(e):
            return []
        logger.warning(f"get_health_history failed for repo_id='{repo_id}': {e}")
        return []


# -- AI Engineering Review -----------------------------------------------------

def insert_repository_review(
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
    record = {
        "id": str(uuid.uuid4()),
        "repo_id": repo_id,
        "user_id": user_id,
        "target_type": target_type,
        "status": status,
        "summary": summary,
        "findings": findings,
        "changed_files": changed_files,
        "commit_hash": commit_hash,
        "request_payload": request_payload or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Attempt the insert directly rather than gating on a potentially stale
    # schema-availability cache (False cache => review never stored => fix 404).
    try:
        result = supabase.table("repository_reviews").insert(record).execute()
        persisted = result.data[0] if result.data else record

        # Update cache on success
        global _REVIEW_SCHEMA_AVAILABLE, _REVIEW_SCHEMA_LAST_CHECKED_AT
        _REVIEW_SCHEMA_AVAILABLE = True
        _REVIEW_SCHEMA_LAST_CHECKED_AT = datetime.now(timezone.utc)

        return persisted
    except Exception as e:
        if _is_missing_review_table_error(e):
            logger.warning(
                f"insert_repository_review: repository_reviews table not found "
                f"(repo_id='{repo_id}'). Apply migration 20260805_repository_reviews.sql. "
                f"Returning in-memory record — fixes will not be retrievable."
            )
            return record
        logger.warning(f"insert_repository_review failed for repo_id='{repo_id}': {e}")
        return record


def list_repository_reviews(
    supabase: Client,
    *,
    repo_id: str,
    user_id: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    if not is_repository_review_schema_available(supabase):
        return []
    try:
        result = (
            supabase.table("repository_reviews")
            .select("*")
            .eq("repo_id", repo_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        if _is_missing_review_table_error(e):
            return []
        logger.warning(f"list_repository_reviews failed for repo_id='{repo_id}': {e}")
        return []


def get_repository_review_by_id(
    supabase: Client,
    *,
    review_id: str,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    # Do NOT rely on the cached schema-availability flag here — a stale False
    # would make every fix/get request fail even when the table exists.
    # Instead, attempt the query and catch missing-table errors gracefully.
    try:
        # Primary query: filter by id + user_id when provided
        query = supabase.table("repository_reviews").select("*").eq("id", review_id)
        if user_id:
            query = query.eq("user_id", user_id)
        result = query.limit(1).execute()
        row = result.data[0] if result.data else None

        if row is None and user_id:
            # Fallback: lookup by id only in case of user_id format mismatch.
            # Caller must verify access via _ensure_repo_access.
            fallback = (
                supabase.table("repository_reviews")
                .select("*")
                .eq("id", review_id)
                .limit(1)
                .execute()
            )
            row = fallback.data[0] if fallback.data else None
            if row:
                logger.info(f"get_repository_review_by_id: found review '{review_id}' via id-only fallback")

        # Update the schema-available cache on success so future calls skip the probe
        global _REVIEW_SCHEMA_AVAILABLE, _REVIEW_SCHEMA_LAST_CHECKED_AT
        _REVIEW_SCHEMA_AVAILABLE = True
        _REVIEW_SCHEMA_LAST_CHECKED_AT = datetime.now(timezone.utc)

        return row
    except Exception as e:
        if _is_missing_review_table_error(e):
            logger.warning(
                f"get_repository_review_by_id: repository_reviews table not found "
                f"(review_id='{review_id}'). Apply migration 20260805_repository_reviews.sql."
            )
            return None
        logger.warning(f"get_repository_review_by_id failed for review_id='{review_id}': {e}")
        return None


def delete_repository_review(
    supabase: Client,
    *,
    review_id: str,
    user_id: str,
) -> bool:
    if not is_repository_review_schema_available(supabase):
        return False
    try:
        supabase.table("repository_reviews").delete().eq("id", review_id).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        if _is_missing_review_table_error(e):
            return False
        logger.warning(f"delete_repository_review failed for review_id='{review_id}': {e}")
        return False
