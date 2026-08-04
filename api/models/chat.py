"""
api/models/chat.py
──────────────────
Pydantic request/response models for chat endpoints.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    repo_id: str
    session_type: str = "quick_ask"


class CreateSessionResponse(BaseModel):
    chat_id: str
    repo_id: str


class SendMessageRequest(BaseModel):
    query: str

    @property
    def query_stripped(self) -> str:
        return self.query.strip()


class RetrievedFile(BaseModel):
    path: str
    score: float


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    role: str                              # "user" | "assistant"
    content: str
    query_mode: Optional[str] = None       # "code_lookup" | "architectural"
    retrieved_files: Optional[List[RetrievedFile]] = None
    latency_ms: Optional[int] = None
    created_at: Optional[datetime] = None


class ChatListItem(BaseModel):
    id: str
    repo_id: str
    user_id: Optional[str] = None
    title: Optional[str] = None
    session_type: Optional[str] = "quick_ask"
    is_pinned: bool = False
    is_favorite: bool = False
    is_archived: bool = False
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateChatRequest(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_favorite: Optional[bool] = None
    is_archived: Optional[bool] = None


class ChatSearchResultItem(BaseModel):
    chat: ChatListItem
    matched_messages: List[MessageResponse] = Field(default_factory=list)
    snippets: List[str] = Field(default_factory=list)


class ChatSearchResponse(BaseModel):
    query: str
    total: int
    items: List[ChatSearchResultItem]


class ConversationSummaryResponse(BaseModel):
    chat_id: str
    repo_id: str
    user_id: str
    title: Optional[str] = None
    executive_summary: Optional[str] = None
    technical_summary: Optional[str] = None
    key_decisions: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)
    risks_identified: List[str] = Field(default_factory=list)
    files_discussed: List[str] = Field(default_factory=list)
    services_discussed: List[str] = Field(default_factory=list)
    modules_discussed: List[str] = Field(default_factory=list)
    classes_discussed: List[str] = Field(default_factory=list)
    apis_discussed: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class ExportResponse(BaseModel):
    filename: str
    format: str
    content_type: str
    content: str
    meta: Dict[str, Any] = Field(default_factory=dict)


class AttachmentCreateRequest(BaseModel):
    filename: str
    storage_path: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class AttachmentUpdateRequest(BaseModel):
    filename: Optional[str] = None
    storage_path: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None


class AttachmentResponse(BaseModel):
    id: str
    chat_id: str
    user_id: str
    filename: str
    storage_path: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


class SavedReportCreateRequest(BaseModel):
    report_type: str
    title: Optional[str] = None
    content: Dict[str, Any] = Field(default_factory=dict)


class SavedReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class SavedReportResponse(BaseModel):
    id: str
    repo_id: str
    user_id: str
    report_type: str
    title: Optional[str] = None
    content: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


# SSE event data shapes (serialised to JSON in the stream)
class TokenEvent(BaseModel):
    type: str = "token"
    content: str


class MetadataEvent(BaseModel):
    type: str = "metadata"
    query_mode: str
    retrieved_files: List[RetrievedFile]
    latency_retrieval_ms: int
    latency_llm_ms: int
    latency_total_ms: int


class DoneEvent(BaseModel):
    type: str = "done"


class ErrorEvent(BaseModel):
    type: str = "error"
    message: str


def format_repository_anchor(item: Dict[str, Any]) -> str:
    summary = item.get("executive_summary") or item.get("technical_summary") or ""
    refs_suffix = _format_anchor_refs_suffix(item)
    return f"- {item.get('title') or 'Previous conversation'}: {summary}{refs_suffix}"


def _format_anchor_refs_suffix(item: Dict[str, Any]) -> str:
    refs = _collect_anchor_refs(item)
    return f" ({'; '.join(refs)})" if refs else ""


def _collect_anchor_refs(item: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    for key, label in (
        ("files_discussed", "files"),
        ("services_discussed", "services"),
        ("apis_discussed", "apis"),
    ):
        values = item.get(key) or []
        if values:
            refs.append(f"{label}=" + ", ".join(values[:3]))
    return refs


def build_repository_memory_context(memory_hits: List[Dict[str, Any]], current_context: str = "") -> str:
    sections: List[str] = []
    if current_context:
        sections.append("CURRENT CONVERSATION CONTEXT:\n" + current_context)
    if memory_hits:
        sections.append(
            "REPOSITORY KNOWLEDGE ANCHORS:\n"
            + "\n".join(format_repository_anchor(item) for item in memory_hits)
        )
    return "\n\n".join(sections)

