"""Evaluation Center service with mode-aware execution, caching, and comparisons."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from dataclasses import asdict
from statistics import mean
from typing import Any, Callable, Dict, List, Optional, Sequence

from supabase import Client

from api.services import supabase_service
from app.config import OLLAMA_EMBED_MODEL, TOP_K_CHUNKS, TOP_K_RERANK, USE_COLBERT, get_repos_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)

PROMPT_VERSION_DEFAULT = os.getenv("EVAL_PROMPT_VERSION", "v1")
STATIC_CONFIDENCE_THRESHOLD_DEFAULT = float(os.getenv("EVAL_STATIC_CONFIDENCE_THRESHOLD", "0.78"))
ESTIMATED_TOKEN_COST_PER_1K_USD = float(os.getenv("EVAL_EST_COST_PER_1K_TOKENS_USD", "0.0012"))


def _repo_root(repo: Dict[str, Any]) -> Optional[str]:
    repos_dir = get_repos_dir()
    for candidate in (repo.get("index_name"), repo.get("name")):
        if not candidate:
            continue
        root = os.path.join(repos_dir, candidate)
        if os.path.isdir(root):
            return root
    return None


def _run_git(repo_root: str, args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout.strip()


def _git_state(repo: Dict[str, Any], requested_branch: Optional[str], requested_commit: Optional[str]) -> Dict[str, str]:
    repo_root = _repo_root(repo)
    if not repo_root:
        return {
            "branch": requested_branch or "unknown",
            "commit_sha": requested_commit or "unknown",
            "repo_root": "",
        }

    branch = requested_branch
    commit_sha = requested_commit
    try:
        if not branch:
            branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
        if not commit_sha:
            commit_sha = _run_git(repo_root, ["rev-parse", "HEAD"]) or "unknown"
    except Exception as err:
        logger.warning(f"git state lookup failed for '{repo_root}': {err}")

    return {
        "branch": branch or "unknown",
        "commit_sha": commit_sha or "unknown",
        "repo_root": repo_root,
    }


def _changed_files_since(repo_root: str, from_commit: Optional[str], to_commit: str) -> List[str]:
    if not repo_root or not to_commit or to_commit == "unknown":
        return []
    if not from_commit or from_commit == "unknown":
        return []
    if from_commit == to_commit:
        return []

    try:
        out = _run_git(repo_root, ["diff", "--name-only", f"{from_commit}..{to_commit}"])
    except Exception as err:
        logger.warning(f"git diff failed for '{repo_root}': {err}")
        return []

    return [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]


def _safe_file_read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _static_analyze(repo_root: str, changed_files: Sequence[str]) -> Dict[str, Any]:
    if not repo_root:
        return {
            "confidence": 0.6,
            "health": 0.6,
            "issues": ["Repository path unavailable for static analysis."],
            "strengths": [],
            "weaknesses": ["Unable to inspect local files."],
            "file_count": 0,
            "issue_density": 0.4,
        }

    paths: List[str] = []
    if changed_files:
        for rel in changed_files[:200]:
            p = os.path.join(repo_root, rel)
            if os.path.isfile(p):
                paths.append(p)
    else:
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "dist", "build", "venv", "__pycache__", ".next"}]
            for name in files:
                if name.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java", ".rs")):
                    paths.append(os.path.join(root, name))
                    if len(paths) >= 250:
                        break
            if len(paths) >= 250:
                break

    if not paths:
        return {
            "confidence": 0.65,
            "health": 0.65,
            "issues": ["No analyzable source files detected."],
            "strengths": [],
            "weaknesses": ["Source files could not be inspected."],
            "file_count": 0,
            "issue_density": 0.35,
        }

    todo_count = 0
    long_line_count = 0
    high_indent_count = 0
    non_empty_lines = 0

    for path in paths:
        text = _safe_file_read(path)
        if not text:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            non_empty_lines += 1
            upper = stripped.upper()
            if "TODO" in upper or "FIXME" in upper or "HACK" in upper:
                todo_count += 1
            if len(line) > 140:
                long_line_count += 1
            if len(line) - len(line.lstrip(" ")) >= 20:
                high_indent_count += 1

    issues_score = min(1.0, (todo_count * 2 + long_line_count + high_indent_count) / max(1.0, non_empty_lines * 0.08))
    health = max(0.1, 1.0 - issues_score)

    strengths: List[str] = []
    weaknesses: List[str] = []
    issues: List[str] = []

    if todo_count == 0:
        strengths.append("No TODO/FIXME markers in inspected files.")
    else:
        weaknesses.append(f"{todo_count} TODO/FIXME/HACK markers found in analyzed scope.")
        issues.append("Reduce TODO/FIXME/HACK markers in active files.")

    if long_line_count <= max(5, len(paths) // 5):
        strengths.append("Most code lines stay within readability limits.")
    else:
        weaknesses.append(f"{long_line_count} long lines (>140 chars) detected.")
        issues.append("Refactor long lines to improve readability.")

    if high_indent_count > max(10, len(paths)):
        weaknesses.append("Nested logic density is high in changed scope.")
        issues.append("Extract nested blocks into focused helper functions.")
    else:
        strengths.append("Control-flow nesting remains manageable.")

    changed_bonus = 0.1 if changed_files else 0.0
    confidence = min(0.95, max(0.55, 0.72 + changed_bonus - (1.0 - health) * 0.5))

    return {
        "confidence": confidence,
        "health": health,
        "issues": issues,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "file_count": len(paths),
        "issue_density": issues_score,
    }


def _overall_score(summary: Dict[str, Any]) -> float:
    return round(
        (
            float(summary.get("hit_rate", 0.0)) * 0.24
            + float(summary.get("mrr", 0.0)) * 0.18
            + float(summary.get("avg_faithfulness", 0.0)) * 0.20
            + float(summary.get("avg_relevancy", 0.0)) * 0.16
            + float(summary.get("mode_accuracy", 0.0)) * 0.12
            + max(0.0, 1.0 - min(1.0, float(summary.get("avg_latency_total", 0.0)) / 4000.0)) * 0.10
        )
        * 100.0,
        2,
    )


def _effort_label(impact: float) -> str:
    if impact >= 7:
        return "High"
    if impact >= 3:
        return "Medium"
    return "Low"


def _build_recommendations(summary: Dict[str, Any], static_report: Dict[str, Any], mode: str) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []

    if float(summary.get("hit_rate", 0.0)) < 0.72:
        recs.append({
            "title": "Improve retrieval recall",
            "description": "Increase retrieval breadth and revisit chunk strategy for weak hit rate.",
            "estimated_impact": round((0.72 - float(summary.get("hit_rate", 0.0))) * 40, 2),
            "one_click_action": {"type": "run_mode", "mode": "deep"},
        })

    if float(summary.get("avg_faithfulness", 0.0)) < 0.75:
        recs.append({
            "title": "Run targeted deep validation",
            "description": "Faithfulness is below target. Trigger Deep mode to refresh grounded response scoring.",
            "estimated_impact": round((0.75 - float(summary.get("avg_faithfulness", 0.0))) * 35, 2),
            "one_click_action": {"type": "run_mode", "mode": "deep"},
        })

    if float(summary.get("avg_latency_total", 0.0)) > 1600:
        recs.append({
            "title": "Reduce end-to-end latency",
            "description": "High average latency detected. Review retrieval depth and reranking scope.",
            "estimated_impact": round(min(12.0, float(summary.get("avg_latency_total", 0.0)) / 400.0), 2),
            "one_click_action": {"type": "open_settings", "target": "retrieval"},
        })

    for issue in static_report.get("issues") or []:
        recs.append({
            "title": issue,
            "description": "Static analysis identified this as a likely source of quality drift.",
            "estimated_impact": 3.8,
            "one_click_action": {"type": "open_explorer", "target": "changed_files"},
        })

    if mode != "deep":
        recs.append({
            "title": "Run a Deep evaluation before release",
            "description": "Deep mode gives full-repository and LLM-backed confidence prior to merge/release.",
            "estimated_impact": 4.2,
            "one_click_action": {"type": "run_mode", "mode": "deep"},
        })

    if not recs:
        recs.append({
            "title": "Maintain current quality baseline",
            "description": "No major weaknesses detected. Monitor trends and run Benchmark weekly.",
            "estimated_impact": 2.0,
            "one_click_action": {"type": "run_mode", "mode": "benchmark"},
        })

    ranked = sorted(recs, key=lambda x: float(x.get("estimated_impact", 0.0)), reverse=True)[:5]
    result: List[Dict[str, Any]] = []
    for i, rec in enumerate(ranked, 1):
        impact = float(rec.get("estimated_impact", 0.0))
        result.append({
            "rank": i,
            "title": rec["title"],
            "description": rec["description"],
            "estimated_impact": impact,
            "expected_effort": _effort_label(impact),
            "one_click_action": rec.get("one_click_action"),
        })
    return result


def _build_ai_summary(summary: Dict[str, Any], static_report: Dict[str, Any], recommendations: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    strength_lines: List[str] = []
    weakness_lines: List[str] = []

    if float(summary.get("hit_rate", 0.0)) >= 0.75:
        strength_lines.append("Retrieval hit rate is stable.")
    else:
        weakness_lines.append("Retrieval hit rate is below target.")

    if float(summary.get("avg_faithfulness", 0.0)) >= 0.75:
        strength_lines.append("Faithfulness remains strong.")
    else:
        weakness_lines.append("Faithfulness should be improved with deeper validation.")

    strength_lines.extend(static_report.get("strengths") or [])
    weakness_lines.extend(static_report.get("weaknesses") or [])

    top_actions = [r["title"] for r in recommendations[:3]]
    estimated_gain = round(sum(float(r.get("estimated_impact", 0.0)) for r in recommendations[:3]) * 0.6, 2)

    return {
        "overall_score": _overall_score(summary),
        "strengths": strength_lines[:5],
        "weaknesses": weakness_lines[:5],
        "top_priority_improvements": top_actions,
        "estimated_score_improvement": estimated_gain,
    }


def _estimate_tokens(mode: str, total_queries: int, ai_calls: int) -> int:
    base = max(1, total_queries)
    if mode == "quick":
        return base * 120
    if mode == "standard":
        return base * 180 + ai_calls * 1400
    if mode == "benchmark":
        return base * 220 + ai_calls * 1500
    return base * 260 + ai_calls * 1800


def _build_efficiency(
    mode: str,
    *,
    cache_hit: bool,
    ai_calls: int,
    static_report: Dict[str, Any],
    total_queries: int,
    prior_runs: int,
) -> Dict[str, Any]:
    token_usage = _estimate_tokens(mode, total_queries, ai_calls)
    estimated_cost = round((token_usage / 1000.0) * ESTIMATED_TOKEN_COST_PER_1K_USD, 6)
    full_deep_tokens = _estimate_tokens("deep", max(10, total_queries), max(10, total_queries))
    deep_cost = (full_deep_tokens / 1000.0) * ESTIMATED_TOKEN_COST_PER_1K_USD
    savings = round(max(0.0, deep_cost - estimated_cost), 6)

    if cache_hit:
        cache_hit_rate = 1.0
    elif prior_runs <= 0:
        cache_hit_rate = 0.0
    else:
        cache_hit_rate = max(0.0, min(0.95, (prior_runs - ai_calls) / max(1, prior_runs)))

    static_share = 1.0 if ai_calls == 0 else max(0.0, min(1.0, float(static_report.get("confidence", 0.0))))

    return {
        "cache_hit_rate": round(cache_hit_rate, 4),
        "ai_calls": ai_calls,
        "static_analysis_percentage": round(static_share, 4),
        "estimated_token_usage": int(token_usage),
        "estimated_cost_usd": estimated_cost,
        "estimated_savings_usd": savings,
    }


def _cache_key(payload: Dict[str, Any]) -> str:
    normalized = {
        "repo_id": payload.get("repo_id"),
        "branch": payload.get("branch") or "unknown",
        "commit_sha": payload.get("commit_sha") or "unknown",
        "embedding_version": payload.get("embedding_version") or OLLAMA_EMBED_MODEL,
        "retrieval_settings": payload.get("retrieval_settings") or {
            "top_k_chunks": TOP_K_CHUNKS,
            "top_k_rerank": TOP_K_RERANK,
            "colbert_enabled": USE_COLBERT,
        },
        "prompt_version": payload.get("prompt_version") or PROMPT_VERSION_DEFAULT,
        "mode": payload.get("mode") or "standard",
    }
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _extract_meta(eval_record: Dict[str, Any]) -> Dict[str, Any]:
    result_json = eval_record.get("result_json") or {}
    return result_json.get("meta") or {}


def _to_summary_dict(eval_record: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "hit_rate": eval_record.get("hit_rate", 0.0),
        "mrr": eval_record.get("mrr", 0.0),
        "avg_faithfulness": eval_record.get("avg_faithfulness", 0.0),
        "avg_relevancy": eval_record.get("avg_relevancy", 0.0),
        "mode_accuracy": eval_record.get("mode_accuracy", 0.0),
        "avg_latency_total": eval_record.get("avg_latency_total", 0.0),
        "avg_latency_retrieval": eval_record.get("avg_latency_retrieval", 0.0),
        "avg_latency_rerank": eval_record.get("avg_latency_rerank", 0.0),
        "avg_latency_llm": eval_record.get("avg_latency_llm", 0.0),
        "colbert_enabled": eval_record.get("colbert_enabled", False),
    }
    payload.update(dict(eval_record.get("result_json") or {}))

    payload.setdefault("id", eval_record.get("id"))
    payload.setdefault("repo_id", eval_record.get("repo_id"))
    payload.setdefault("created_at", eval_record.get("created_at"))
    payload.setdefault("total_queries", payload.get("total_queries") or 0)
    payload.setdefault("mode", (_extract_meta(eval_record).get("mode") or "standard"))
    payload.setdefault("cache_key", _extract_meta(eval_record).get("cache_key"))
    payload.setdefault("cache_hit", bool(_extract_meta(eval_record).get("cache_hit", False)))
    payload.setdefault("ai_summary", payload.get("ai_summary") or None)
    payload.setdefault("top_recommendations", payload.get("top_recommendations") or [])
    raw_efficiency = payload.get("efficiency")
    if raw_efficiency:
        payload["efficiency"] = {
            "cache_hit_rate": float(raw_efficiency.get("cache_hit_rate", 0.0)),
            "ai_calls": int(raw_efficiency.get("ai_calls", 0)),
            "static_analysis_percentage": float(raw_efficiency.get("static_analysis_percentage", 0.0)),
            "estimated_token_usage": int(raw_efficiency.get("estimated_token_usage", 0)),
            "estimated_cost_usd": float(raw_efficiency.get("estimated_cost_usd", 0.0)),
            "estimated_savings_usd": float(raw_efficiency.get("estimated_savings_usd", 0.0)),
        }
    else:
        payload["efficiency"] = None
    payload.setdefault("comparison", payload.get("comparison") or None)
    return payload


def _make_comparison(current: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not baseline:
        return None

    return {
        "baseline_eval_id": baseline.get("id"),
        "overall_score_delta": round(_overall_score(current) - _overall_score(baseline), 2),
        "hit_rate_delta": round(float(current.get("hit_rate", 0.0)) - float(baseline.get("hit_rate", 0.0)), 4),
        "faithfulness_delta": round(float(current.get("avg_faithfulness", 0.0)) - float(baseline.get("avg_faithfulness", 0.0)), 4),
        "latency_delta_ms": round(float(current.get("avg_latency_total", 0.0)) - float(baseline.get("avg_latency_total", 0.0)), 2),
        "estimated_cost_delta_usd": round(
            float((current.get("efficiency") or {}).get("estimated_cost_usd", 0.0))
            - float((baseline.get("efficiency") or {}).get("estimated_cost_usd", 0.0)),
            6,
        ),
    }


async def run_evaluation_center(
    *,
    supabase: Client,
    repo: Dict[str, Any],
    repo_id: str,
    user_id: str,
    index_name: str,
    mode: str,
    requested_branch: Optional[str],
    requested_commit: Optional[str],
    embedding_version: Optional[str],
    retrieval_settings: Optional[Dict[str, Any]],
    prompt_version: Optional[str],
    static_confidence_threshold: Optional[float],
    emit_progress: Callable[[str], None],
) -> Dict[str, Any]:
    threshold = float(static_confidence_threshold or STATIC_CONFIDENCE_THRESHOLD_DEFAULT)
    threshold = max(0.0, min(1.0, threshold))

    git_state = await asyncio.get_event_loop().run_in_executor(None, _git_state, repo, requested_branch, requested_commit)
    emit_progress(f"Mode selected: {mode}. Captured branch={git_state['branch']} commit={git_state['commit_sha'][:12]}.")

    cache_payload = {
        "repo_id": repo_id,
        "branch": git_state["branch"],
        "commit_sha": git_state["commit_sha"],
        "embedding_version": embedding_version,
        "retrieval_settings": retrieval_settings,
        "prompt_version": prompt_version,
        "mode": mode,
    }
    cache_key = _cache_key(cache_payload)

    prior_runs = supabase_service.get_recent_evaluations(supabase, repo_id=repo_id, limit=25)
    latest = prior_runs[0] if prior_runs else None

    cache_match = None
    for row in prior_runs:
        meta = _extract_meta(row)
        if meta.get("cache_key") == cache_key:
            cache_match = row
            break

    if cache_match and mode != "deep":
        emit_progress("Cache hit: reusing persisted evaluation result.")
        cached = _to_summary_dict(cache_match)
        cached_meta = (cached.get("meta") or {})
        cached_meta.update({
            "cache_hit": True,
            "cache_key": cache_key,
            "mode": mode,
        })
        cached["meta"] = cached_meta
        cached["mode"] = mode
        cached["cache_key"] = cache_key
        cached["cache_hit"] = True
        return cached

    baseline_summary = _to_summary_dict(latest) if latest else None
    previous_commit = (_extract_meta(latest).get("commit_sha") if latest else None)
    changed_files = await asyncio.get_event_loop().run_in_executor(
        None,
        _changed_files_since,
        git_state.get("repo_root") or "",
        previous_commit,
        git_state.get("commit_sha") or "",
    )

    if changed_files:
        emit_progress(f"Detected {len(changed_files)} changed files since previous run.")
    else:
        emit_progress("No changed files detected relative to previous commit.")

    static_scope = changed_files if mode == "standard" else []
    static_report = await asyncio.get_event_loop().run_in_executor(
        None,
        _static_analyze,
        git_state.get("repo_root") or "",
        static_scope,
    )
    emit_progress(
        f"Static analysis complete (confidence={static_report['confidence']:.2f}, files={static_report['file_count']})."
    )

    should_call_llm = False
    llm_reason = ""

    if mode == "deep":
        should_call_llm = True
        llm_reason = "Deep mode explicitly requested"
    elif mode == "benchmark":
        should_call_llm = bool(changed_files) or static_report["confidence"] < threshold
        llm_reason = "Benchmark mode compares against latest and refreshes on changes" if should_call_llm else "Benchmark mode reused static results"
    elif mode == "standard":
        if static_report["confidence"] < threshold:
            should_call_llm = True
            llm_reason = f"Static confidence {static_report['confidence']:.2f} is below threshold {threshold:.2f}"
        elif changed_files and latest:
            should_call_llm = True
            llm_reason = "Changed files invalidate previous findings"
    else:  # quick
        should_call_llm = False
        llm_reason = "Quick mode uses cache/static analysis only"

    summary: Dict[str, Any]
    ai_calls = 0
    if should_call_llm:
        emit_progress(f"Invoking full AI evaluation: {llm_reason}.")
        from app.llm.llm_client import configure_llamaindex_settings

        def _run_full_eval() -> Dict[str, Any]:
            configure_llamaindex_settings()
            from evaluate import run_evaluation

            result = run_evaluation(index_name)
            if result is None:
                raise RuntimeError("Evaluation returned no results")
            return asdict(result)

        summary = await asyncio.get_event_loop().run_in_executor(None, lambda: _run_full_eval())
        ai_calls = int(summary.get("total_queries") or 0)
    else:
        emit_progress("Skipping AI evaluation and deriving result from static analysis + baseline metrics.")
        base = baseline_summary or {
            "hit_rate": 0.62,
            "mrr": 0.55,
            "avg_faithfulness": 0.65,
            "avg_relevancy": 0.66,
            "mode_accuracy": 0.7,
            "avg_latency_total": 850.0,
            "avg_latency_retrieval": 230.0,
            "avg_latency_rerank": 80.0,
            "avg_latency_llm": 0.0,
            "colbert_enabled": USE_COLBERT,
            "total_queries": 0,
            "results": [],
        }
        drift = (1.0 - float(static_report.get("health", 0.6))) * 0.08
        summary = {
            "hit_rate": max(0.0, min(1.0, float(base.get("hit_rate", 0.0)) - drift)),
            "mrr": max(0.0, min(1.0, float(base.get("mrr", 0.0)) - drift * 0.8)),
            "avg_faithfulness": max(0.0, min(1.0, float(base.get("avg_faithfulness", 0.0)) - drift * 0.6)),
            "avg_relevancy": max(0.0, min(1.0, float(base.get("avg_relevancy", 0.0)) - drift * 0.6)),
            "mode_accuracy": max(0.0, min(1.0, float(base.get("mode_accuracy", 0.0)) - drift * 0.5)),
            "avg_keyword_hit": float(base.get("avg_keyword_hit", mean([0.7, float(static_report.get("health", 0.6))]))),
            "avg_latency_total": float(base.get("avg_latency_total", 850.0)),
            "avg_latency_retrieval": float(base.get("avg_latency_retrieval", 230.0)),
            "avg_latency_rerank": float(base.get("avg_latency_rerank", 80.0)),
            "avg_latency_llm": 0.0,
            "colbert_enabled": bool(base.get("colbert_enabled", USE_COLBERT)),
            "total_queries": int(base.get("total_queries", 0)),
            "results": [],
        }

    recommendations = _build_recommendations(summary, static_report, mode)
    ai_summary = _build_ai_summary(summary, static_report, recommendations)
    efficiency = _build_efficiency(
        mode,
        cache_hit=False,
        ai_calls=ai_calls,
        static_report=static_report,
        total_queries=int(summary.get("total_queries") or 0),
        prior_runs=len(prior_runs),
    )

    summary["ai_summary"] = ai_summary
    summary["top_recommendations"] = recommendations
    summary["efficiency"] = efficiency
    summary["mode"] = mode
    summary["cache_key"] = cache_key
    summary["cache_hit"] = False

    meta = {
        "mode": mode,
        "branch": git_state["branch"],
        "commit_sha": git_state["commit_sha"],
        "embedding_version": embedding_version or OLLAMA_EMBED_MODEL,
        "retrieval_settings": retrieval_settings or {
            "top_k_chunks": TOP_K_CHUNKS,
            "top_k_rerank": TOP_K_RERANK,
            "colbert_enabled": USE_COLBERT,
        },
        "prompt_version": prompt_version or PROMPT_VERSION_DEFAULT,
        "cache_key": cache_key,
        "cache_hit": False,
        "llm_called": should_call_llm,
        "llm_reason": llm_reason,
        "static_confidence": static_report.get("confidence"),
        "static_confidence_threshold": threshold,
        "changed_files": changed_files[:200],
    }
    summary["meta"] = meta

    baseline_comp = baseline_summary if (baseline_summary and baseline_summary.get("id") != summary.get("id")) else None
    summary["comparison"] = _make_comparison(summary, baseline_comp)

    return summary


def hydrate_eval_response(eval_record: Dict[str, Any]) -> Dict[str, Any]:
    return _to_summary_dict(eval_record)


def build_eval_history_points(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for row in rows:
        summary = _to_summary_dict(row)
        points.append({
            "id": str(row.get("id") or ""),
            "created_at": row.get("created_at"),
            "overall_score": _overall_score(summary),
            "hit_rate": float(summary.get("hit_rate", 0.0)),
            "avg_faithfulness": float(summary.get("avg_faithfulness", 0.0)),
            "avg_latency_total": float(summary.get("avg_latency_total", 0.0)),
            "cache_hit_rate": float((summary.get("efficiency") or {}).get("cache_hit_rate", 0.0)),
            "estimated_ai_cost_usd": float((summary.get("efficiency") or {}).get("estimated_cost_usd", 0.0)),
        })
    return points


def build_comparison_payload(current: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    return _make_comparison(_to_summary_dict(current), _to_summary_dict(baseline)) or {
        "baseline_eval_id": None,
        "overall_score_delta": 0.0,
        "hit_rate_delta": 0.0,
        "faithfulness_delta": 0.0,
        "latency_delta_ms": 0.0,
        "estimated_cost_delta_usd": 0.0,
    }
