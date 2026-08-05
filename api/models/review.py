"""
api/models/review.py
--------------------
Pydantic contracts for AI engineering review endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


ReviewSeverity = Literal["low", "medium", "high", "critical"]
ReviewTargetType = Literal["file", "files", "commit", "pr"]


class ReviewFinding(BaseModel):
    id: str
    severity: ReviewSeverity
    file: str
    code_area: str
    finding: str
    recommendation: str
    suggested_fix: str
    risk_level: Literal["low", "medium", "high"]
    impact: str = ""
    complexity: str = ""
    estimated_effort: str = ""
    expected_benefit: str = ""


class ReviewRunResponse(BaseModel):
    review_id: str
    repo_id: str
    target_type: ReviewTargetType
    status: str
    summary: str
    findings: List[ReviewFinding] = Field(default_factory=list)
    changed_files: List[str] = Field(default_factory=list)
    commit_hash: Optional[str] = None
    created_at: Optional[datetime] = None


class ReviewHistoryItem(BaseModel):
    review_id: str
    repo_id: str
    target_type: ReviewTargetType
    status: str
    summary: str
    commit_hash: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class ReviewListResponse(BaseModel):
    items: List[ReviewHistoryItem] = Field(default_factory=list)


class ReviewFileRequest(BaseModel):
    repo_id: str
    filename: str
    prompt: Optional[str] = None


class ReviewFilesRequest(BaseModel):
    repo_id: str
    files: List[str] = Field(default_factory=list)
    prompt: Optional[str] = None


class ReviewCommitRequest(BaseModel):
    repo_id: str
    commit_hash: str
    prompt: Optional[str] = None


class ReviewPullRequestRequest(BaseModel):
    repo_id: str
    changed_files: List[str] = Field(default_factory=list)
    diff: str = ""
    prompt: Optional[str] = None


class ReviewFixRequest(BaseModel):
    review_id: str
    finding_id: Optional[str] = None
    # Direct finding payload — used as fallback when the DB record is unavailable
    finding: Optional[str] = None
    file: Optional[str] = None
    code_area: Optional[str] = None
    recommendation: Optional[str] = None
    repo_id: Optional[str] = None


class ReviewFixResponse(BaseModel):
    review_id: str
    suggested_fix: str
    target_file: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

