"""Pydantic models for repository explorer endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel, Field


class ExplorerTreeNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "folder"]
    has_children: bool
    size: int
    modified_at: Optional[str] = None
    language: str
    health: str
    ai_indicator: str
    git_status: str = ""
    is_modified: bool = False


class ExplorerTreeResponse(BaseModel):
    repo_root: str
    path: str
    nodes: List[ExplorerTreeNode]
    truncated: bool = False
    count: int


class ExplorerFileResponse(BaseModel):
    path: str
    language: str
    content: str
    sha256: str
    summary: str
    complexity: int
    health: str
    dependencies: Dict[str, Any]
    classes: List[str]
    functions: List[str]
    imports: List[str]
    line_count: int
    size: int


class ExplorerReviewFileRequest(BaseModel):
    path: str = Field(min_length=1)
    review_type: str = "review"
    prompt: str = ""


class ExplorerReviewFilesRequest(BaseModel):
    paths: List[str] = Field(default_factory=list, min_length=1, max_length=20)
    review_type: str = "review"
    prompt: str = ""


class ExplorerFixGenerateRequest(BaseModel):
    path: str = Field(min_length=1)
    finding: str = Field(min_length=1)
    recommendation: str = ""


class ExplorerFixApplyRequest(BaseModel):
    fix_id: str = Field(min_length=1)
    expected_sha256: Optional[str] = None
    run_validation: bool = True


class ExplorerTestDiscoverRequest(BaseModel):
    paths: List[str] = Field(default_factory=list, min_length=1, max_length=25)


class ExplorerTestRunRequest(BaseModel):
    tests: List[str] = Field(default_factory=list, min_length=1, max_length=80)
    timeout_seconds: int = Field(default=55, ge=5, le=59)


class ExplorerConversationEntryRequest(BaseModel):
    path: str = Field(min_length=1)
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1)

