"""
api/routers/health.py
---------------------
Repository health intelligence API endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.health import (
    HealthCategoryDetailResponse,
    HealthHistoryPoint,
    HealthHistoryResponse,
    HealthLatestResponse,
    HealthRunResponse,
)
from api.routers._repo_access import ensure_repo_access
from api.services import supabase_service
from api.services.repository_health_engine import RepositoryHealthEngine
from app.utils.logger import get_logger

router = APIRouter()
engine = RepositoryHealthEngine()
logger = get_logger(__name__)

_TRANSIENT_HEALTH_RUNS: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
_MAX_TRANSIENT_RUNS_PER_REPO = 50


def _transient_key(repo_id: str, user_id: str) -> Tuple[str, str]:
    return (repo_id, user_id)


def _append_transient_run(repo_id: str, user_id: str, run_payload: Dict[str, Any]) -> None:
    key = _transient_key(repo_id, user_id)
    runs = _TRANSIENT_HEALTH_RUNS.get(key, [])
    runs.append(run_payload)
    _TRANSIENT_HEALTH_RUNS[key] = runs[-_MAX_TRANSIENT_RUNS_PER_REPO:]


def _latest_transient_run(repo_id: str, user_id: str) -> Dict[str, Any] | None:
    runs = _TRANSIENT_HEALTH_RUNS.get(_transient_key(repo_id, user_id), [])
    return runs[-1] if runs else None


def _transient_category_score_map(run_payload: Dict[str, Any]) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for row in run_payload.get("categories", []):
        category = row.get("category")
        if not category:
            continue
        scores[str(category)] = int(row.get("score", 0))
    return scores


def _transient_problem_titles(run_payload: Dict[str, Any]) -> List[str]:
    titles: List[str] = []
    for finding in run_payload.get("findings", []):
        if finding.get("finding_type") == "problem" and finding.get("title"):
            titles.append(str(finding.get("title")))
    return titles


def _health_run_from_payload(payload: Dict[str, Any]) -> HealthRunResponse:
    return HealthRunResponse.model_validate(payload)


def _load_previous_health_context(
    supabase: Client,
    repo_id: str,
    user_id: str,
) -> tuple[dict | None, list[str] | None, int | None]:
    latest_run, previous_scores, previous_findings = supabase_service.get_health_comparison_context(
        supabase,
        repo_id=repo_id,
        user_id=user_id,
    )
    if latest_run and latest_run.get("repository_health") is not None:
        previous_overall = int(latest_run["repository_health"])
        return previous_scores, previous_findings, previous_overall

    transient_latest = _latest_transient_run(repo_id, user_id)
    if not transient_latest:
        return None, None, None

    transient_scores = _transient_category_score_map(transient_latest)
    transient_findings = _transient_problem_titles(transient_latest)
    transient_overall = int(transient_latest.get("top_level", {}).get("repository_health", 0))
    return transient_scores or None, transient_findings or None, transient_overall


def _build_history_points(supabase: Client, runs: list[dict], user_id: str) -> list[HealthHistoryPoint]:
    points: list[HealthHistoryPoint] = []
    for run in runs:
        category_map = supabase_service.get_health_category_score_map(supabase, run_id=run["id"], user_id=user_id)
        points.append(
            HealthHistoryPoint(
                run_id=run["id"],
                created_at=run["created_at"],
                repository_health=run["repository_health"],
                grade=run["grade"],
                category_scores=category_map,
            )
        )
    return points


def _build_transient_history_points(repo_id: str, user_id: str, limit: int) -> list[HealthHistoryPoint]:
    runs = _TRANSIENT_HEALTH_RUNS.get(_transient_key(repo_id, user_id), [])
    if not runs:
        return []

    points: list[HealthHistoryPoint] = []
    for run_payload in list(reversed(runs[-max(1, limit):])):
        top = run_payload.get("top_level", {})
        points.append(
            HealthHistoryPoint(
                run_id=str(run_payload.get("run_id")),
                created_at=run_payload.get("generated_at") or datetime.now(timezone.utc),
                repository_health=int(top.get("repository_health", 0)),
                grade=str(top.get("grade", "F")),
                category_scores=_transient_category_score_map(run_payload),
            )
        )
    return points


@router.post("/{repo_id}/health/run", response_model=HealthRunResponse)
async def run_repository_health_analysis(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    repo = ensure_repo_access(supabase, repo_id, user_id)
    previous_scores, previous_findings, previous_overall = _load_previous_health_context(supabase, repo_id, user_id)

    run_payload = engine.run(
        repo=repo,
        previous_scores=previous_scores,
        previous_findings=previous_findings,
        previous_overall_score=previous_overall,
    )


    try:
        run_record = supabase_service.insert_health_run(
            supabase,
            repo_id=repo_id,
            user_id=user_id,
            top_level=run_payload["top_level"],
            executive_summary=run_payload["executive_summary"],
            strengths=run_payload["strengths"],
            weaknesses=run_payload["weaknesses"],
            critical_risks=run_payload["critical_risks"],
            architecture_risks=run_payload["architecture_risks"],
            security_risks=run_payload["security_risks"],
            performance_risks=run_payload["performance_risks"],
            recommended_sprint=run_payload["recommended_sprint"],
            improved_categories=run_payload["improved_categories"],
            declining_categories=run_payload["declining_categories"],
            new_risks=run_payload["new_risks"],
            resolved_risks=run_payload["resolved_risks"],
            benchmark=run_payload["benchmark"],
        )

        supabase_service.insert_health_category_scores(
            supabase,
            run_id=run_record["id"],
            repo_id=repo_id,
            user_id=user_id,
            categories=run_payload["categories"],
        )
        supabase_service.insert_health_findings(
            supabase,
            run_id=run_record["id"],
            repo_id=repo_id,
            user_id=user_id,
            findings=run_payload["findings"],
        )
        supabase_service.insert_health_recommendations(
            supabase,
            run_id=run_record["id"],
            repo_id=repo_id,
            user_id=user_id,
            recommendations=run_payload["recommendations"],
        )

        response = _hydrate_health_run_response(supabase, run_record["id"], repo_id, user_id)
        payload = response.model_dump()
        _append_transient_run(repo_id, user_id, payload)
        return response
    except Exception as e:
        logger.warning(f"Health run persistence unavailable, returning transient result: {e}")
        transient_response = _build_transient_health_run_response(repo_id=repo_id, run_payload=run_payload)
        payload = transient_response.model_dump()
        _append_transient_run(repo_id, user_id, payload)
        return transient_response


@router.get("/{repo_id}/health/latest", response_model=HealthLatestResponse)
async def get_latest_repository_health(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ensure_repo_access(supabase, repo_id, user_id)

    run = supabase_service.get_latest_health_run(supabase, repo_id=repo_id, user_id=user_id)
    if not run:
        transient_latest = _latest_transient_run(repo_id, user_id)
        if not transient_latest:
            return HealthLatestResponse(repo_id=repo_id, latest=None)
        return HealthLatestResponse(repo_id=repo_id, latest=_health_run_from_payload(transient_latest))
    return HealthLatestResponse(repo_id=repo_id, latest=_hydrate_health_run_response(supabase, run["id"], repo_id, user_id))


@router.get("/{repo_id}/health/history", response_model=HealthHistoryResponse)
async def get_repository_health_history(
    repo_id: str,
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=30, ge=1, le=100),
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ensure_repo_access(supabase, repo_id, user_id)

    runs = supabase_service.get_health_history(supabase, repo_id=repo_id, user_id=user_id, days=days, limit=limit)
    points = _build_history_points(supabase, runs, user_id) if runs else _build_transient_history_points(repo_id, user_id, limit)

    latest = runs[0] if runs else None
    return HealthHistoryResponse(
        repo_id=repo_id,
        points=points,
        improved_categories=(latest or {}).get("improved_categories") or [],
        declining_categories=(latest or {}).get("declining_categories") or [],
        new_risks=(latest or {}).get("new_risks") or [],
        resolved_risks=(latest or {}).get("resolved_risks") or [],
    )


@router.get("/{repo_id}/health/categories/{category}", response_model=HealthCategoryDetailResponse)
async def get_repository_health_category_details(
    repo_id: str,
    category: str,
    run_id: str | None = None,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ensure_repo_access(supabase, repo_id, user_id)

    selected_run_id = run_id
    if not selected_run_id:
        latest = supabase_service.get_latest_health_run(supabase, repo_id=repo_id, user_id=user_id)
        if not latest:
            raise HTTPException(status_code=404, detail="No health run found")
        selected_run_id = latest["id"]

    score = supabase_service.get_health_category_score(supabase, run_id=selected_run_id, user_id=user_id, category=category)
    if not score:
        raise HTTPException(status_code=404, detail="Category not found in selected run")

    findings = supabase_service.get_health_findings(
        supabase,
        run_id=selected_run_id,
        user_id=user_id,
        category=category,
    )

    return HealthCategoryDetailResponse(
        repo_id=repo_id,
        run_id=selected_run_id,
        category=category,
        score=score,
        findings=findings,
    )


def _hydrate_health_run_response(supabase: Client, run_id: str, repo_id: str, user_id: str) -> HealthRunResponse:
    run = supabase_service.get_health_run_by_id(supabase, run_id=run_id, user_id=user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Health run not found")

    categories = supabase_service.get_health_category_scores(supabase, run_id=run_id, user_id=user_id)
    findings = supabase_service.get_health_findings(supabase, run_id=run_id, user_id=user_id)
    recommendations = supabase_service.get_health_recommendations(supabase, run_id=run_id, user_id=user_id)

    return HealthRunResponse(
        run_id=run_id,
        repo_id=repo_id,
        generated_at=run["created_at"],
        top_level={
            "repository_health": run["repository_health"],
            "grade": run["grade"],
            "status": run["status"],
            "trend": run.get("trend") or 0,
            "last_analysis": run["created_at"],
            "repository_size": run.get("repository_size") or "Small",
            "language_detection": run.get("language_detection") or [],
            "framework_detection": run.get("framework_detection") or [],
        },
        categories=categories,
        findings=findings,
        recommendations=recommendations,
        executive_summary=run.get("executive_summary") or "",
        strengths=run.get("strengths") or [],
        weaknesses=run.get("weaknesses") or [],
        critical_risks=run.get("critical_risks") or [],
        architecture_risks=run.get("architecture_risks") or [],
        security_risks=run.get("security_risks") or [],
        performance_risks=run.get("performance_risks") or [],
        recommended_sprint=run.get("recommended_sprint") or [],
    )


def _build_transient_health_run_response(repo_id: str, run_payload: dict) -> HealthRunResponse:
    return HealthRunResponse(
        run_id=f"transient-{uuid.uuid4()}",
        repo_id=repo_id,
        generated_at=datetime.now(timezone.utc),
        top_level=run_payload["top_level"],
        categories=run_payload["categories"],
        findings=run_payload["findings"],
        recommendations=run_payload["recommendations"],
        executive_summary=run_payload.get("executive_summary") or "",
        strengths=run_payload.get("strengths") or [],
        weaknesses=run_payload.get("weaknesses") or [],
        critical_risks=run_payload.get("critical_risks") or [],
        architecture_risks=run_payload.get("architecture_risks") or [],
        security_risks=run_payload.get("security_risks") or [],
        performance_risks=run_payload.get("performance_risks") or [],
        recommended_sprint=run_payload.get("recommended_sprint") or [],
    )
