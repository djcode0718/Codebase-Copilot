"""
api/models/repo.py
──────────────────
Pydantic request/response models for repository endpoints.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, field_validator


class IndexRepoRequest(BaseModel):
    source: str  # GitHub URL or local path

    @field_validator("source")
    @classmethod
    def source_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source must not be empty")
        return v.strip()


class IndexRepoResponse(BaseModel):
    repo_id: str
    index_name: str
    status: str  # "indexing" | "ready" | "failed"
    message: str


class RepoStatusResponse(BaseModel):
    id: str
    name: str
    source_url: str
    index_name: str
    status: str           # "indexing" | "ready" | "failed"
    file_count: Optional[int] = None
    node_count: Optional[int] = None
    llm_provider: Optional[str] = None
    created_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None


class IndexProgressEvent(BaseModel):
    step: str        # "cloning" | "filtering" | "parsing" | "embedding" | "indexing" | "summary" | "done" | "error"
    message: str
    progress: int    # 0–100
    file_count: Optional[int] = None
    node_count: Optional[int] = None
