"""
api/models/chat.py
──────────────────
Pydantic request/response models for chat endpoints.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    repo_id: str


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
    title: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
