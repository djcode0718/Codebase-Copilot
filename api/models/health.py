"""
api/models/health.py
--------------------
Pydantic contracts for repository health intelligence endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


HealthCategory = Literal[
    "Architecture",
    "Security",
    "Testing",
    "Documentation",
    "Performance",
    "Maintainability",
    "Technical Debt",
    "Dependencies",
    "Code Quality",
    "Scalability",
    "Observability",
    "Developer Experience",
]


class HealthFinding(BaseModel):
    id: str
    category: HealthCategory
    finding_type: Literal["problem", "positive"]
    severity: Literal["low", "medium", "high", "critical"]
    title: str
    details: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommendation: Optional[str] = None
    affected_files: List[str] = Field(default_factory=list)
    affected_modules: List[str] = Field(default_factory=list)
    expected_score_gain: int = 0


class HealthCategoryScore(BaseModel):
    category: HealthCategory
    score: int
    grade: str
    trend: int = 0
    explanation: str
    detected_problems: List[str] = Field(default_factory=list)
    positive_findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)
    affected_modules: List[str] = Field(default_factory=list)


class HealthRecommendation(BaseModel):
    rank: int
    title: str
    description: str
    category: HealthCategory
    estimated_effort: str
    expected_score_gain: int
    impact_score: float
    action_items: List[str] = Field(default_factory=list)
    affected_files: List[str] = Field(default_factory=list)


class HealthTopLevel(BaseModel):
    repository_health: int
    grade: str
    status: str
    trend: int
    last_analysis: datetime
    repository_size: Literal["Small", "Medium", "Large"]
    language_detection: List[str] = Field(default_factory=list)
    framework_detection: List[str] = Field(default_factory=list)


class HealthRunResponse(BaseModel):
    run_id: str
    repo_id: str
    generated_at: datetime
    top_level: HealthTopLevel
    categories: List[HealthCategoryScore]
    findings: List[HealthFinding]
    recommendations: List[HealthRecommendation]
    executive_summary: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    critical_risks: List[str] = Field(default_factory=list)
    architecture_risks: List[str] = Field(default_factory=list)
    security_risks: List[str] = Field(default_factory=list)
    performance_risks: List[str] = Field(default_factory=list)
    recommended_sprint: List[str] = Field(default_factory=list)


class HealthHistoryPoint(BaseModel):
    run_id: str
    created_at: datetime
    repository_health: int
    grade: str
    category_scores: Dict[str, int] = Field(default_factory=dict)


class HealthHistoryResponse(BaseModel):
    repo_id: str
    points: List[HealthHistoryPoint]
    improved_categories: List[str] = Field(default_factory=list)
    declining_categories: List[str] = Field(default_factory=list)
    new_risks: List[str] = Field(default_factory=list)
    resolved_risks: List[str] = Field(default_factory=list)


class HealthCategoryDetailResponse(BaseModel):
    repo_id: str
    run_id: str
    category: HealthCategory
    score: HealthCategoryScore
    findings: List[HealthFinding]


class HealthLatestResponse(BaseModel):
    repo_id: str
    latest: Optional[HealthRunResponse] = None

