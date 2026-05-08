"""
api/models/eval.py
──────────────────
Pydantic models for evaluation endpoints.
"""

from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel


class RunEvalRequest(BaseModel):
    repo_id: str
    index_name: str


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
    colbert_enabled: bool
    total_queries: int
    created_at: Optional[datetime] = None
