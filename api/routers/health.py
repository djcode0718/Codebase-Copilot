"""
api/routers/health.py
---------------------
Repository health intelligence API endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
import json
import os
import threading
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.models.health import (
    HealthCategoryDetailResponse,
    HealthHistoryPoint,
    HealthHistoryResponse,
    HealthLatestResponse,
    RecommendationStatusUpdateRequest,
    RecommendationStatusUpdateResponse,
    HealthRunResponse,
)
from api.routers._repo_access import ensure_repo_access
from api.services import supabase_service
from api.services.repository_health_engine import RepositoryHealthEngine
from app.utils.logger import get_logger
from app.config import DATA_DIR

router = APIRouter()
engine = RepositoryHealthEngine()
logger = get_logger(__name__)

_TRANSIENT_HEALTH_RUNS: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
_MAX_TRANSIENT_RUNS_PER_REPO = 50
_TRANSIENT_STORE_PATH = os.path.join(DATA_DIR, "health_transient_runs.json")
_TRANSIENT_STORE_LOCK = threading.Lock()
_TRANSIENT_STORE_LOADED = False


def _transient_key(repo_id: str, user_id: str) -> Tuple[str, str]:
    return (repo_id, user_id)


def _serialize_transient_key(repo_id: str, user_id: str) -> str:
    return f"{repo_id}::{user_id}"


def _deserialize_transient_key(value: str) -> Tuple[str, str] | None:
    if "::" not in value:
        return None
    repo_id, user_id = value.split("::", 1)
    if not repo_id or not user_id:
        return None
    return repo_id, user_id


def _load_transient_store_if_needed() -> None:
    global _TRANSIENT_STORE_LOADED
    if _TRANSIENT_STORE_LOADED:
        return

    with _TRANSIENT_STORE_LOCK:
        if _TRANSIENT_STORE_LOADED:
            return
        if not os.path.exists(_TRANSIENT_STORE_PATH):
            _TRANSIENT_STORE_LOADED = True
            return
        try:
            with open(_TRANSIENT_STORE_PATH, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                for key, runs in raw.items():
                    parsed_key = _deserialize_transient_key(str(key))
                    if not parsed_key or not isinstance(runs, list):
                        continue
                    _TRANSIENT_HEALTH_RUNS[parsed_key] = [r for r in runs if isinstance(r, dict)][-_MAX_TRANSIENT_RUNS_PER_REPO:]
        except Exception as e:
            logger.warning(f"Failed to load transient health store: {e}")
        finally:
            _TRANSIENT_STORE_LOADED = True


def _save_transient_store() -> None:
    with _TRANSIENT_STORE_LOCK:
        try:
            os.makedirs(os.path.dirname(_TRANSIENT_STORE_PATH), exist_ok=True)
            payload: Dict[str, List[Dict[str, Any]]] = {}
            for (repo_id, user_id), runs in _TRANSIENT_HEALTH_RUNS.items():
                payload[_serialize_transient_key(repo_id, user_id)] = runs[-_MAX_TRANSIENT_RUNS_PER_REPO:]
            with open(_TRANSIENT_STORE_PATH, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True)
        except Exception as e:
            logger.warning(f"Failed to persist transient health store: {e}")


def _append_transient_run(repo_id: str, user_id: str, run_payload: Dict[str, Any]) -> None:
    _load_transient_store_if_needed()
    key = _transient_key(repo_id, user_id)
    runs = _TRANSIENT_HEALTH_RUNS.get(key, [])
    runs.append(run_payload)
    _TRANSIENT_HEALTH_RUNS[key] = runs[-_MAX_TRANSIENT_RUNS_PER_REPO:]
    _save_transient_store()


def _latest_transient_run(repo_id: str, user_id: str) -> Dict[str, Any] | None:
    _load_transient_store_if_needed()
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

    # Use in-memory transient history for trend carryover. Avoid loading
    # persisted fallback snapshots here, which can pollute a fresh baseline.
    transient_runs = _TRANSIENT_HEALTH_RUNS.get(_transient_key(repo_id, user_id), [])
    transient_latest = transient_runs[-1] if transient_runs else None
    if not transient_latest:
        return None, None, None

    transient_scores = _transient_category_score_map(transient_latest)
    transient_findings = _transient_problem_titles(transient_latest)
    transient_overall = int(transient_latest.get("top_level", {}).get("repository_health", 0))
    return transient_scores or None, transient_findings or None, transient_overall


def _build_analysis_context(repo: Dict[str, Any], run_payload: Dict[str, Any]) -> Dict[str, Any]:
    top = run_payload.get("top_level", {})
    return {
        "repository": repo.get("name") or repo.get("index_name") or repo.get("id"),
        "branch": repo.get("active_branch") or repo.get("default_branch") or "unknown",
        "commit_sha": repo.get("active_commit_sha") or "unknown",
        "index_version": repo.get("index_name") or "unknown",
        "indexed_at": repo.get("indexed_at"),
        "analysis_version": "health-v2",
        "analysis_generated_at": top.get("last_analysis"),
    }


def _build_history_state(points_count: int) -> Dict[str, Any]:
    enough = points_count > 1
    return {
        "has_sufficient_history": enough,
        "baseline_message": None if enough else "Health baseline established. Future analyses will appear here.",
        "data_points": points_count,
    }


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


def _severity_breakdown(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    out = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        if finding.get("finding_type") != "problem":
            continue
        sev = str(finding.get("severity") or "low").lower()
        if sev in out:
            out[sev] += 1
    return out


def _checks_for_category(category: str) -> List[str]:
    checks = {
        "Architecture": ["dependency_graph_scan", "cycle_detection", "module_boundary_analysis"],
        "Security": ["auth_guard_scan", "secret_pattern_scan", "sensitive_log_scan"],
        "Testing": ["test_coverage_proxy", "test_mapping_scan", "negative_test_signal_scan"],
        "Documentation": ["readme_presence", "doc_coverage_scan"],
        "Performance": ["async_blocking_scan", "caching_signal_scan"],
        "Maintainability": ["function_complexity_scan", "duplication_signal_scan"],
        "Technical Debt": ["todo_fixme_scan", "legacy_marker_scan"],
        "Dependencies": ["manifest_scan", "version_pin_scan"],
        "Code Quality": ["lint_signal_scan", "style_signal_scan"],
        "Scalability": ["concurrency_signal_scan", "queue_usage_scan"],
        "Observability": ["logging_signal_scan", "tracing_signal_scan"],
        "Developer Experience": ["onboarding_signal_scan", "tooling_script_scan"],
    }
    return checks.get(category, ["heuristic_repository_scan"])


def _enrich_category_score(score: Dict[str, Any], *, findings: List[Dict[str, Any]], run: Dict[str, Any]) -> Dict[str, Any]:
    analysis_context = run.get("analysis_context") or {}
    row = dict(score)
    row.setdefault("confidence", 0.0)
    row.setdefault("files_analyzed", len(row.get("affected_files") or []) or len(findings))
    row.setdefault("checks_performed", _checks_for_category(str(row.get("category") or "")))
    row.setdefault("findings_count", len(findings))
    row.setdefault("severity_breakdown", _severity_breakdown(findings))
    row.setdefault("analysis_timestamp", run.get("created_at"))
    row.setdefault("branch", analysis_context.get("branch") or "unknown")
    row.setdefault("commit_sha", analysis_context.get("commit_sha") or "unknown")
    return row


def _build_transient_history_points(repo_id: str, user_id: str, limit: int) -> list[HealthHistoryPoint]:
    _load_transient_store_if_needed()
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
    analysis_context = _build_analysis_context(repo, run_payload)
    run_payload["analysis_context"] = analysis_context


    try:
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
                analysis_context=analysis_context,
            )
        except TypeError:
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

        persisted_recommendations = supabase_service.get_health_recommendations(
            supabase,
            run_id=run_record["id"],
            user_id=user_id,
        )
        response = HealthRunResponse(
            run_id=run_record["id"],
            repo_id=repo_id,
            generated_at=run_record.get("created_at") or datetime.now(timezone.utc),
            top_level=run_payload["top_level"],
            categories=run_payload["categories"],
            findings=run_payload["findings"],
            recommendations=persisted_recommendations or run_payload["recommendations"],
            analysis_context=analysis_context,
            history_state=_build_history_state(2 if previous_overall is not None else 1),
            executive_summary=run_payload.get("executive_summary") or "",
            strengths=run_payload.get("strengths") or [],
            weaknesses=run_payload.get("weaknesses") or [],
            critical_risks=run_payload.get("critical_risks") or [],
            architecture_risks=run_payload.get("architecture_risks") or [],
            security_risks=run_payload.get("security_risks") or [],
            performance_risks=run_payload.get("performance_risks") or [],
            recommended_sprint=run_payload.get("recommended_sprint") or [],
        )
        payload = response.model_dump(mode="json")
        _append_transient_run(repo_id, user_id, payload)
        return response
    except Exception as e:
        logger.warning(f"Health run persistence unavailable, returning transient result: {e}")
        transient_response = _build_transient_health_run_response(repo_id=repo_id, run_payload=run_payload)
        payload = transient_response.model_dump(mode="json")
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
    history_state = _build_history_state(len(points))
    return HealthHistoryResponse(
        repo_id=repo_id,
        points=points,
        has_sufficient_history=history_state["has_sufficient_history"],
        baseline_message=history_state["baseline_message"],
        data_points=history_state["data_points"],
        improved_categories=(latest or {}).get("improved_categories") or [],
        declining_categories=(latest or {}).get("declining_categories") or [],
        new_risks=(latest or {}).get("new_risks") or [],
        resolved_risks=(latest or {}).get("resolved_risks") or [],
    )


@router.patch("/{repo_id}/health/recommendations/{recommendation_id}/status", response_model=RecommendationStatusUpdateResponse)
async def update_recommendation_status(
    repo_id: str,
    recommendation_id: str,
    body: RecommendationStatusUpdateRequest,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ensure_repo_access(supabase, repo_id, user_id)

    latest = supabase_service.get_latest_health_run(supabase, repo_id=repo_id, user_id=user_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No health run found")

    recs = supabase_service.get_health_recommendations(supabase, run_id=latest["id"], user_id=user_id)
    target = next((rec for rec in recs if str(rec.get("recommendation_id")) == recommendation_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    fingerprint = str(target.get("fingerprint") or "")
    if not fingerprint:
        raise HTTPException(status_code=400, detail="Recommendation fingerprint unavailable")

    requested_status = str(body.status).strip().upper()
    ignore_reason = body.reason if requested_status in {"IGNORED", "DISMISSED"} else None

    saved = supabase_service.upsert_health_recommendation_state(
        supabase,
        repo_id=repo_id,
        user_id=user_id,
        fingerprint=fingerprint,
        category=str(target.get("category") or ""),
        title=str(target.get("title") or ""),
        status=body.status,
        dismissed_reason=ignore_reason,
    )
    persisted_status = str((saved or {}).get("status") or body.status)
    updated_at = (saved or {}).get("updated_at") or datetime.now(timezone.utc)
    return RecommendationStatusUpdateResponse(
        recommendation_id=recommendation_id,
        fingerprint=fingerprint,
        status=persisted_status,
        reason=body.reason if persisted_status == "IGNORED" else None,
        updated_at=updated_at,
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
    run = supabase_service.get_health_run_by_id(supabase, run_id=selected_run_id, user_id=user_id) or {}
    enriched_score = _enrich_category_score(score, findings=findings, run=run)

    return HealthCategoryDetailResponse(
        repo_id=repo_id,
        run_id=selected_run_id,
        category=category,
        score=enriched_score,
        findings=findings,
    )


def _hydrate_health_run_response(supabase: Client, run_id: str, repo_id: str, user_id: str) -> HealthRunResponse:
    run = supabase_service.get_health_run_by_id(supabase, run_id=run_id, user_id=user_id)
    if not run:
        raise HTTPException(status_code=404, detail="Health run not found")

    categories = supabase_service.get_health_category_scores(supabase, run_id=run_id, user_id=user_id)
    findings = supabase_service.get_health_findings(supabase, run_id=run_id, user_id=user_id)
    recommendations = supabase_service.get_health_recommendations(supabase, run_id=run_id, user_id=user_id)
    recent_runs = supabase_service.get_recent_health_runs(supabase, repo_id=repo_id, user_id=user_id, limit=2)

    findings_by_category: Dict[str, List[Dict[str, Any]]] = {}
    for finding in findings:
        category = str(finding.get("category") or "")
        if not category:
            continue
        findings_by_category.setdefault(category, []).append(finding)

    enriched_categories = [
        _enrich_category_score(
            score,
            findings=findings_by_category.get(str(score.get("category") or ""), []),
            run=run,
        )
        for score in categories
    ]

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
        categories=enriched_categories,
        findings=findings,
        recommendations=recommendations,
        analysis_context=run.get("analysis_context") or {
            "repository": repo_id,
            "branch": "unknown",
            "commit_sha": "unknown",
            "index_version": run.get("repo_id") or "unknown",
            "indexed_at": None,
            "analysis_version": "health-v2",
        },
        history_state=_build_history_state(len(recent_runs)),
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
    analysis_context = run_payload.get("analysis_context") or {
        "repository": repo_id,
        "branch": "unknown",
        "commit_sha": "unknown",
        "index_version": "transient",
        "indexed_at": None,
        "analysis_version": "health-v2",
    }
    return HealthRunResponse(
        run_id=f"transient-{uuid.uuid4()}",
        repo_id=repo_id,
        generated_at=datetime.now(timezone.utc),
        top_level=run_payload["top_level"],
        categories=run_payload["categories"],
        findings=run_payload["findings"],
        recommendations=run_payload["recommendations"],
        analysis_context=analysis_context,
        history_state=_build_history_state(1),
        executive_summary=run_payload.get("executive_summary") or "",
        strengths=run_payload.get("strengths") or [],
        weaknesses=run_payload.get("weaknesses") or [],
        critical_risks=run_payload.get("critical_risks") or [],
        architecture_risks=run_payload.get("architecture_risks") or [],
        security_risks=run_payload.get("security_risks") or [],
        performance_risks=run_payload.get("performance_risks") or [],
        recommended_sprint=run_payload.get("recommended_sprint") or [],
    )
