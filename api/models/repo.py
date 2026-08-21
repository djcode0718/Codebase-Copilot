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
    active_branch: Optional[str] = None
    default_branch: Optional[str] = None
    active_commit_sha: Optional[str] = None


class BranchCheckoutRequest(BaseModel):
    branch: str
    pull_latest: bool = True

    @field_validator("branch")
    @classmethod
    def branch_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("branch must not be empty")
        return v.strip()


class BranchPullRequest(BaseModel):
    branch: Optional[str] = None


class BranchListResponse(BaseModel):
    current_branch: str
    default_branch: str
    recent_branches: list[str]
    local_branches: list[str]
    remote_branches: list[str]


class BranchStatusResponse(BaseModel):
    current_branch: str
    default_branch: str
    last_commit: str
    author: str
    commit_sha: str
    short_commit_sha: str
    ahead: int
    behind: int
    changed_files: int
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0
    changed_paths: list[str]
    captured_at: str
    indexed_at: Optional[str] = None
    index_status: str
    evaluation_status: str = "unknown"
    health_score: Optional[float] = None
    sync_status: str = "unknown"


class BranchActionResponse(BaseModel):
    message: str
    current_branch: str
    commit_sha: str
    status: BranchStatusResponse


class BranchComparisonRequest(BaseModel):
    base_branch: str
    target_branch: str


class MergeReadinessResponse(BaseModel):
    overall_score: float
    blocking_issues: list[str]
    warnings: list[str]
    suggested_reviewers: list[str]
    estimated_review_time_minutes: int
    deployment_risk: str
    safe_to_merge: bool


class BranchComparisonResponse(BaseModel):
    base_branch: str
    target_branch: str
    changed_files: int
    sample_changed_files: list[str]
    architecture_changes: int
    security_changes: int
    performance_changes: int
    technical_debt_changes: int
    api_changes: int
    database_changes: int
    business_logic_changes: int
    dependency_changes: int
    testing_changes: int = 0
    health_impact_delta: int = 0
    security_impact_delta: int = 0
    test_impact_delta: int = 0
    impact_summary: str = ""
    risk_assessment: str
    merge_readiness: MergeReadinessResponse
    ai_executive_summary: str


class IndexProgressEvent(BaseModel):
    step: str        # "cloning" | "filtering" | "parsing" | "embedding" | "indexing" | "summary" | "done" | "error"
    message: str
    progress: int    # 0–100
    file_count: Optional[int] = None
    node_count: Optional[int] = None
