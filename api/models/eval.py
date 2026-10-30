"""
api/models/eval.py
──────────────────
Pydantic models for evaluation endpoints.
"""

from typing import Optional, List, Any, Dict, Literal
from datetime import datetime
from pydantic import BaseModel, Field


EvalMode = Literal["quick", "standard", "deep", "benchmark"]


class RunEvalRequest(BaseModel):
    repo_id: str
    index_name: str
    mode: EvalMode = "standard"
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    embedding_version: Optional[str] = None
    retrieval_settings: Optional[Dict[str, Any]] = None
    prompt_version: Optional[str] = None
    static_confidence_threshold: Optional[float] = None


class EvalAiSummary(BaseModel):
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    top_priority_improvements: List[str]
    estimated_score_improvement: float


class EvalRecommendation(BaseModel):
    rank: int
    title: str
    description: str
    estimated_impact: float
    expected_effort: Literal["Low", "Medium", "High"]
    one_click_action: Optional[Dict[str, Any]] = None


class EvalEfficiency(BaseModel):
    cache_hit_rate: float
    ai_calls: int
    static_analysis_percentage: float
    estimated_token_usage: int
    estimated_cost_usd: float
    estimated_savings_usd: float


class EvalComparison(BaseModel):
    baseline_eval_id: Optional[str] = None
    overall_score_delta: float
    hit_rate_delta: float
    faithfulness_delta: float
    latency_delta_ms: float
    estimated_cost_delta_usd: float


class EvalTrendPoint(BaseModel):
    id: str
    created_at: datetime
    overall_score: float
    hit_rate: float
    avg_faithfulness: float
    avg_latency_total: float
    cache_hit_rate: float
    estimated_ai_cost_usd: float


class EvalHistoryResponse(BaseModel):
    repo_id: str
    points: List[EvalTrendPoint]


class EvalSummaryResponse(BaseModel):
    id: Optional[str] = None
    repo_id: str
    hit_rate: float
    mrr: float
    avg_faithfulness: float
    avg_relevancy: float
    mode_accuracy: float
    avg_latency_total: float
    avg_latency_retrieval: float
    avg_latency_rerank: float
    avg_latency_llm: float
    colbert_enabled: bool = Field(default=False, description="Deprecated. Use cross_encoder_enabled instead.")
    cross_encoder_enabled: bool = Field(default=False, description="Whether Cross-Encoder reranking was used.")
    total_queries: int
    mode: EvalMode = "standard"
    cache_key: Optional[str] = None
    cache_hit: bool = False
    ai_summary: Optional[EvalAiSummary] = None
    top_recommendations: List[EvalRecommendation] = Field(default_factory=list)
    efficiency: Optional[EvalEfficiency] = None
    comparison: Optional[EvalComparison] = None
    created_at: Optional[datetime] = None


class EvalComparisonResponse(BaseModel):
    repo_id: str
    current: Optional[EvalSummaryResponse] = None
    baseline: Optional[EvalSummaryResponse] = None
    comparison: Optional[EvalComparison] = None

