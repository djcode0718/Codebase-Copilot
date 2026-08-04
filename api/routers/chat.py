"""
api/routers/chat.py
────────────────────
Chat endpoints:

  POST   /api/chat/session                   Create a new chat session
  POST   /api/chat/{chat_id}/message/stream  SSE streaming response
  GET    /api/chat/{chat_id}/messages        Full message history
  GET    /api/chat/list?repo_id=...          List chats for a repo
  DELETE /api/chat/{chat_id}                 Delete a chat + all messages
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.chat import (
    CreateSessionRequest,
    CreateSessionResponse,
    SendMessageRequest,
    MessageResponse,
    ChatListItem,
    UpdateChatRequest,
    ChatSearchResponse,
    ChatSearchResultItem,
    ConversationSummaryResponse,
    ExportResponse,
    AttachmentCreateRequest,
    AttachmentUpdateRequest,
    AttachmentResponse,
    SavedReportCreateRequest,
    SavedReportUpdateRequest,
    SavedReportResponse,
)
from api.services import supabase_service
from api.services.chat_session_service import (
    create_quick_ask_session,
    get_or_create_main_session,
    update_session_flags,
    soft_delete_session,
    restore_session,
)
from api.services.chat_search_service import search_repository_conversations
from api.services.repository_memory_service import refresh_session_memory
from api.services.export_service import build_export_payload
from api.services.repository_knowledge_service import get_repository_knowledge_context
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _safe_stream_error_message(err: Exception) -> str:
    msg = str(err).lower()
    if (
        "could not find the table" in msg
        or "schema cache" in msg
        or "pgrst" in msg
        or "conversation_summaries" in msg
    ):
        return (
            "I hit a temporary repository memory issue. "
            "Please ask a repository-specific question about a file, function, class, or module."
        )
    return (
        "I ran into an internal error while answering. "
        "Please retry with a repository-specific question (file, function, class, or module)."
    )


def _ensure_repo_access(supabase: Client, user_id: str, repo_id: str) -> dict:
    from api.services.supabase_service import get_repo
    repo = get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return repo


def _ensure_chat_access(supabase: Client, user_id: str, chat_id: str) -> dict:
    chat = supabase_service.get_chat(supabase, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if chat["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return chat


def _ensure_report_access(supabase: Client, user_id: str, report_id: str) -> dict:
    report = supabase_service.get_saved_report(supabase, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Saved report not found")
    if report["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return report


def _get_stream_chat_response_callable():
    from api.services.chat_service import stream_chat_response
    return stream_chat_response


@router.post("/session", response_model=CreateSessionResponse)
async def create_chat_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Create a new chat session for a given repository.
    Returns the chat_id which the client uses for all subsequent messages.
    """
    repo = _ensure_repo_access(supabase, user_id, body.repo_id)
    if repo["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Repository is not ready yet (status: {repo['status']}). Wait for indexing to complete."
        )

    if (body.session_type or "quick_ask") == "main":
        chat = get_or_create_main_session(supabase, user_id=user_id, repo_id=body.repo_id)
    else:
        chat = create_quick_ask_session(supabase, user_id=user_id, repo_id=body.repo_id)

    return CreateSessionResponse(
        chat_id=chat["id"],
        repo_id=body.repo_id,
    )


@router.post("/session/quick-ask", response_model=CreateSessionResponse)
async def create_quick_ask(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, body.repo_id)
    chat = create_quick_ask_session(supabase, user_id=user_id, repo_id=body.repo_id)
    return CreateSessionResponse(chat_id=chat["id"], repo_id=body.repo_id)


@router.post("/session/main", response_model=CreateSessionResponse)
async def create_or_resume_main_session(
    body: CreateSessionRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, body.repo_id)
    chat = get_or_create_main_session(supabase, user_id=user_id, repo_id=body.repo_id)
    return CreateSessionResponse(chat_id=chat["id"], repo_id=body.repo_id)


@router.post("/{chat_id}/message/stream")
async def stream_message(
    chat_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Stream an AI response for a user message.

    SSE events:
        data: {"type": "token",    "content": "..."}
        data: {"type": "metadata", "query_mode": "code_lookup", "retrieved_files": [...], ...}
        data: {"type": "done"}
        data: {"type": "error",   "message": "..."}

    After streaming completes, persists both the user message and
    assistant response to Supabase asynchronously.
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must not be empty")

    # Verify chat + ownership
    chat = _ensure_chat_access(supabase, user_id, chat_id)

    # Get repo to find index_name
    repo = _ensure_repo_access(supabase, user_id, chat["repo_id"])
    if repo["status"] != "ready":
        raise HTTPException(status_code=400, detail="Repository index is not ready")

    index_name = repo["index_name"]
    repo_id = repo["id"]
    memory_hits = get_repository_knowledge_context(
        supabase,
        user_id=user_id,
        repo_id=repo_id,
        query=query,
        chat_id=chat_id,
        max_items=3,
    )
    memory_context = "\n\n".join(
        f"- {item.get('title') or 'Previous conversation'}: {item.get('executive_summary') or item.get('technical_summary') or ''}"
        for item in memory_hits
    )

    # Lazy import keeps API startup resilient when optional AI deps are not installed yet.
    try:
        stream_chat_response = _get_stream_chat_response_callable()
    except ModuleNotFoundError as import_err:
        raise HTTPException(
            status_code=503,
            detail=(
                "Chat dependencies are not installed. "
                "Install runtime requirements and retry."
            ),
        ) from import_err

    # Persist user message to DB immediately (before streaming)
    # This ensures it shows even if the stream fails halfway
    try:
        supabase_service.save_message(supabase, chat_id, role="user", content=query)
    except Exception as e:
        logger.warning(f"Failed to persist user message: {e}")

    # Update chat title on first message
    try:
        existing_messages = supabase_service.get_messages_for_chat(supabase, chat_id)
        if len(existing_messages) <= 1:  # only the user msg we just saved
            title = query[:60] + ("..." if len(query) > 60 else "")
            supabase_service.update_chat_title(supabase, chat_id, title)
    except Exception:
        pass

    async def event_generator():
        """
        Wraps the streaming chat response and collects metadata for DB persistence.
        """
        full_response = ""
        metadata_event = None

        try:
            async for sse_line in stream_chat_response(query, index_name, repo_id, chat_id, memory_context=memory_context):
                yield sse_line

                # Parse events to collect full response and metadata
                if sse_line.startswith("data: "):
                    try:
                        event = json.loads(sse_line[6:])
                        if event.get("type") == "token":
                            full_response += event.get("content", "")
                        elif event.get("type") == "metadata":
                            metadata_event = event
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error during SSE chat stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': _safe_stream_error_message(e)})}\n\n"

        # After stream: persist assistant message to DB
        if full_response:
            try:
                supabase_service.save_message(
                    supabase,
                    chat_id,
                    role="assistant",
                    content=full_response,
                    query_mode=metadata_event.get("query_mode") if metadata_event else None,
                    retrieved_files=metadata_event.get("retrieved_files") if metadata_event else None,
                    latency_ms=metadata_event.get("latency_total_ms") if metadata_event else None,
                )
                refresh_session_memory(supabase, chat=chat)
            except Exception as db_err:
                logger.warning(f"Failed to persist assistant message: {db_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions", response_model=List[ChatListItem])
async def list_sessions(
    repo_id: str = Query(..., description="Repository ID"),
    include_archived: bool = Query(True, description="Include archived sessions"),
    include_deleted: bool = Query(False, description="Include soft-deleted sessions"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Optional text search on title/summary"),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    if search:
        results = search_repository_conversations(
            supabase,
            user_id=user_id,
            repo_id=repo_id,
            query=search,
            limit=limit,
            offset=offset,
        )
        return [ChatListItem(**r["chat"]) for r in results]

    chats = supabase_service.get_chats_for_repo(
        supabase,
        repo_id,
        include_archived=include_archived,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )
    return [ChatListItem(**c) for c in chats]


@router.get("/list", response_model=List[ChatListItem])
async def list_chats(
    repo_id: str = Query(..., description="Repository ID"),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Backward-compatible alias for listing active chats."""
    _ensure_repo_access(supabase, user_id, repo_id)
    chats = supabase_service.get_chats_for_repo(supabase, repo_id, include_archived=True, include_deleted=False, limit=100, offset=0)
    return [ChatListItem(**c) for c in chats]


@router.get("/search", response_model=ChatSearchResponse)
async def search_chats(
    repo_id: str = Query(..., description="Repository ID"),
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    items = search_repository_conversations(
        supabase,
        user_id=user_id,
        repo_id=repo_id,
        query=q,
        limit=limit,
        offset=offset,
    )
    data = [ChatSearchResultItem(chat=ChatListItem(**item["chat"]), matched_messages=[MessageResponse(**m) for m in item["matched_messages"]], snippets=item["snippets"]) for item in items]
    return ChatSearchResponse(query=q, total=len(data), items=data)


@router.get("/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    chat_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Return all messages for a chat session in chronological order.
    Used to restore chat history when the user reopens a session.
    """
    _ensure_chat_access(supabase, user_id, chat_id)

    messages = supabase_service.get_messages_for_chat(supabase, chat_id)
    return [MessageResponse(**m) for m in messages]


@router.patch("/{chat_id}", response_model=ChatListItem)
async def update_chat_session(
    chat_id: str,
    body: UpdateChatRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    chat = _ensure_chat_access(supabase, user_id, chat_id)
    if body.is_archived is False and chat.get("deleted_at"):
        restore_session(supabase, chat_id)
    update_session_flags(
        supabase,
        chat_id,
        title=body.title,
        is_pinned=body.is_pinned,
        is_favorite=body.is_favorite,
        is_archived=body.is_archived,
    )
    updated = _ensure_chat_access(supabase, user_id, chat_id)
    return ChatListItem(**updated)


@router.get("/{chat_id}/summary", response_model=ConversationSummaryResponse)
async def get_chat_summary(
    chat_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    chat = _ensure_chat_access(supabase, user_id, chat_id)
    summary = supabase_service.get_conversation_summary(supabase, chat_id)
    if not summary:
        generated = refresh_session_memory(supabase, chat=chat)
        summary = {"chat_id": chat_id, "repo_id": chat["repo_id"], "user_id": user_id, **generated}

    tags = supabase_service.get_tags_for_chat(supabase, chat_id)
    payload = {
        "chat_id": chat_id,
        "repo_id": chat["repo_id"],
        "user_id": user_id,
        "title": chat.get("title"),
        **summary,
        "tags": tags or summary.get("tags") or [],
    }
    return ConversationSummaryResponse(**payload)


@router.post("/{chat_id}/summary/regenerate", response_model=ConversationSummaryResponse)
async def regenerate_chat_summary(
    chat_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    chat = _ensure_chat_access(supabase, user_id, chat_id)
    refresh_session_memory(supabase, chat=chat)
    summary = supabase_service.get_conversation_summary(supabase, chat_id) or {}
    tags = supabase_service.get_tags_for_chat(supabase, chat_id)
    return ConversationSummaryResponse(
        chat_id=chat_id,
        repo_id=chat["repo_id"],
        user_id=user_id,
        title=chat.get("title"),
        tags=tags or summary.get("tags") or [],
        **summary,
    )


@router.get("/export", response_model=ExportResponse)
async def export_repo_memory(
    repo_id: str = Query(..., description="Repository ID"),
    format: str = Query("md", pattern="^(md|txt|json|pdf|docx)$"),
    chat_ids: Optional[str] = Query(None, description="Comma-separated chat IDs"),
    include_archived: bool = Query(True),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = _ensure_repo_access(supabase, user_id, repo_id)
    selected = {cid.strip() for cid in (chat_ids or "").split(",") if cid.strip()}
    chats = supabase_service.get_chats_for_repo(
        supabase,
        repo_id,
        include_archived=include_archived,
        include_deleted=False,
        limit=500,
        offset=0,
    )
    sessions = []
    for chat in chats:
        if selected and chat["id"] not in selected:
            continue
        if chat["user_id"] != user_id:
            continue
        sessions.append(
            {
                **chat,
                "messages": supabase_service.get_messages_for_chat(supabase, chat["id"]),
                "summary": supabase_service.get_conversation_summary(supabase, chat["id"]),
                "tags": supabase_service.get_tags_for_chat(supabase, chat["id"]),
            }
        )

    export_payload = build_export_payload(repo_name=repo.get("name", "repository"), format_name=format, sessions=sessions)
    return ExportResponse(**export_payload)


@router.post("/{chat_id}/attachments", response_model=AttachmentResponse)
async def create_attachment(
    chat_id: str,
    body: AttachmentCreateRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_chat_access(supabase, user_id, chat_id)
    record = supabase_service.create_attachment(
        supabase,
        chat_id=chat_id,
        user_id=user_id,
        filename=body.filename,
        storage_path=body.storage_path,
        mime_type=body.mime_type,
        file_size=body.file_size,
    )
    return AttachmentResponse(**record)


@router.get("/{chat_id}/attachments", response_model=List[AttachmentResponse])
async def list_attachments(
    chat_id: str,
    include_deleted: bool = Query(False),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_chat_access(supabase, user_id, chat_id)
    rows = supabase_service.get_attachments_for_chat(supabase, chat_id=chat_id, include_deleted=include_deleted)
    return [AttachmentResponse(**row) for row in rows]


@router.get("/attachments/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(
    attachment_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    row = supabase_service.get_attachment(supabase, attachment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return AttachmentResponse(**row)


@router.patch("/attachments/{attachment_id}", response_model=AttachmentResponse)
async def update_attachment(
    attachment_id: str,
    body: AttachmentUpdateRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    row = supabase_service.get_attachment(supabase, attachment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    updates = body.model_dump(exclude_none=True)
    if updates:
        supabase_service.update_attachment(supabase, attachment_id, updates)
    refreshed = supabase_service.get_attachment(supabase, attachment_id) or {**row, **updates}
    return AttachmentResponse(**refreshed)


@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    hard_delete: bool = Query(False),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    row = supabase_service.get_attachment(supabase, attachment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if hard_delete:
        supabase.table("attachments").delete().eq("id", attachment_id).execute()
        return {"message": "Attachment permanently deleted."}
    supabase_service.soft_delete_attachment(supabase, attachment_id)
    return {"message": "Attachment deleted."}


@router.post("/repo/{repo_id}/reports", response_model=SavedReportResponse)
async def create_saved_report(
    repo_id: str,
    body: SavedReportCreateRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    report = supabase_service.create_saved_report(
        supabase,
        repo_id=repo_id,
        user_id=user_id,
        report_type=body.report_type,
        title=body.title,
        content=body.content,
    )
    return SavedReportResponse(**report)


@router.get("/repo/{repo_id}/reports", response_model=List[SavedReportResponse])
async def list_saved_reports(
    repo_id: str,
    include_deleted: bool = Query(False),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    reports = supabase_service.get_saved_reports_for_repo(
        supabase,
        repo_id=repo_id,
        user_id=user_id,
        include_deleted=include_deleted,
    )
    return [SavedReportResponse(**report) for report in reports]


@router.get("/reports/{report_id}", response_model=SavedReportResponse)
async def get_saved_report(
    report_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    report = _ensure_report_access(supabase, user_id, report_id)
    return SavedReportResponse(**report)


@router.patch("/reports/{report_id}", response_model=SavedReportResponse)
async def update_saved_report(
    report_id: str,
    body: SavedReportUpdateRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    report = _ensure_report_access(supabase, user_id, report_id)
    updates = body.model_dump(exclude_none=True)
    if updates:
        supabase_service.update_saved_report(supabase, report_id, updates)
    refreshed = supabase_service.get_saved_report(supabase, report_id) or {**report, **updates}
    return SavedReportResponse(**refreshed)


@router.delete("/reports/{report_id}")
async def delete_saved_report(
    report_id: str,
    hard_delete: bool = Query(False),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_report_access(supabase, user_id, report_id)
    if hard_delete:
        supabase.table("saved_reports").delete().eq("id", report_id).execute()
        return {"message": "Report permanently deleted."}
    supabase_service.soft_delete_saved_report(supabase, report_id)
    return {"message": "Report deleted."}


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    hard_delete: bool = Query(False, description="Permanently delete the chat and messages"),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Soft-delete by default; optional hard-delete for permanent removal."""
    _ensure_chat_access(supabase, user_id, chat_id)
    if hard_delete:
        supabase_service.delete_chat(supabase, chat_id)
        return {"message": "Chat permanently deleted."}
    soft_delete_session(supabase, chat_id)
    return {"message": "Chat moved to deleted state."}


@router.post("/{chat_id}/restore")
async def restore_chat(
    chat_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_chat_access(supabase, user_id, chat_id)
    restore_session(supabase, chat_id)
    return {"message": "Chat restored."}


@router.delete("/repo/{repo_id}/all")
async def delete_all_repo_chats(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    _ensure_repo_access(supabase, user_id, repo_id)
    supabase_service.delete_all_chats_for_repo(supabase, repo_id=repo_id, user_id=user_id)
    return {"message": "All chats soft-deleted for repository."}
