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

import asyncio
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
)
from api.services import supabase_service
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


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
    # Verify the repo exists and belongs to this user
    from api.services.supabase_service import get_repo
    repo = get_repo(supabase, body.repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if repo["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Repository is not ready yet (status: {repo['status']}). Wait for indexing to complete."
        )

    chat = supabase_service.create_chat(
        supabase,
        user_id=user_id,
        repo_id=body.repo_id,
    )

    return CreateSessionResponse(
        chat_id=chat["id"],
        repo_id=body.repo_id,
    )


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
    chat = supabase_service.get_chat(supabase, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if chat["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get repo to find index_name
    from api.services.supabase_service import get_repo
    repo = get_repo(supabase, chat["repo_id"])
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found for this chat")
    if repo["status"] != "ready":
        raise HTTPException(status_code=400, detail="Repository index is not ready")

    index_name = repo["index_name"]
    repo_id = repo["id"]

    # Lazy import keeps API startup resilient when optional AI deps are not installed yet.
    try:
        from api.services.chat_service import stream_chat_response
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
            async for sse_line in stream_chat_response(query, index_name, repo_id, chat_id):
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
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

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


@router.get("/list", response_model=List[ChatListItem])
async def list_chats(
    repo_id: str = Query(..., description="Repository ID"),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """List all chat sessions for a given repository, newest first."""
    chats = supabase_service.get_chats_for_repo(supabase, repo_id)
    return [ChatListItem(**c) for c in chats]


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
    chat = supabase_service.get_chat(supabase, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if chat["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = supabase_service.get_messages_for_chat(supabase, chat_id)
    return [MessageResponse(**m) for m in messages]


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Delete a chat session and all its messages."""
    chat = supabase_service.get_chat(supabase, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if chat["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    supabase_service.delete_chat(supabase, chat_id)
    return {"message": "Chat deleted successfully."}
