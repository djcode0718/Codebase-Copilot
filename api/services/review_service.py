"""File-scoped engineering review service."""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_repos_dir
from app.utils.logger import get_logger
from api.services.review_suggestion_service import generate_review_payload

logger = get_logger(__name__)

_MAX_FILE_CHARS = 18000
_MAX_FILES = 25


@dataclass
class ReviewTarget:
    path: str
    content: str


def _resolve_repo_root(index_name: str, repo_name: str) -> str:
    repos_dir = get_repos_dir()
    preferred = os.path.join(repos_dir, index_name)
    if os.path.isdir(preferred):
        return preferred
    fallback = os.path.join(repos_dir, repo_name)
    return fallback


def _safe_join_repo_path(repo_root: str, relative_path: str) -> Optional[str]:
    candidate = os.path.normpath(os.path.join(repo_root, relative_path))
    repo_root_norm = os.path.normpath(repo_root)
    if not candidate.startswith(repo_root_norm):
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate


def _read_repo_file(repo_root: str, relative_path: str) -> Optional[ReviewTarget]:
    abs_path = _safe_join_repo_path(repo_root, relative_path)
    if not abs_path:
        return None
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(_MAX_FILE_CHARS)
        return ReviewTarget(path=relative_path, content=content)
    except Exception as err:
        logger.warning(f"Failed to read review target '{relative_path}': {err}")
        return None


def _extract_code_smells(target: ReviewTarget) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    lines = target.content.splitlines()

    if any("TODO" in ln or "FIXME" in ln for ln in lines):
        findings.append({
            "id": str(uuid.uuid4()),
            "severity": "low",
            "file": target.path,
            "code_area": "maintainability",
            "finding": "Deferred TODO/FIXME markers found.",
            "recommendation": "Resolve or track TODO/FIXME with a ticket reference.",
            "suggested_fix": "Replace TODO/FIXME with implemented behavior or issue key.",
            "risk_level": "low",
            "impact": "Untracked debt can accumulate.",
            "complexity": "low",
            "estimated_effort": "0.5-1h",
            "expected_benefit": "Cleaner maintenance backlog.",
        })

    if any("except Exception" in ln for ln in lines):
        findings.append({
            "id": str(uuid.uuid4()),
            "severity": "medium",
            "file": target.path,
            "code_area": "error handling",
            "finding": "Broad exception handling detected.",
            "recommendation": "Catch specific exception types and preserve actionable context.",
            "suggested_fix": "Narrow except blocks to expected exceptions and add bounded fallback behavior.",
            "risk_level": "medium",
            "impact": "Hidden runtime failures are harder to debug.",
            "complexity": "medium",
            "estimated_effort": "1-2h",
            "expected_benefit": "Improved reliability and diagnosability.",
        })

    if any(re.search(r"\b(eval|exec)\(", ln) for ln in lines):
        findings.append({
            "id": str(uuid.uuid4()),
            "severity": "high",
            "file": target.path,
            "code_area": "security",
            "finding": "Dynamic code execution surface detected.",
            "recommendation": "Remove eval/exec usage or gate with strict sanitization.",
            "suggested_fix": "Replace eval/exec with deterministic parsing or controlled mapping.",
            "risk_level": "high",
            "impact": "Potential code injection risk.",
            "complexity": "medium",
            "estimated_effort": "2-4h",
            "expected_benefit": "Reduced exploitability.",
        })

    if any(len(ln) > 160 for ln in lines):
        findings.append({
            "id": str(uuid.uuid4()),
            "severity": "low",
            "file": target.path,
            "code_area": "readability",
            "finding": "Very long lines reduce readability.",
            "recommendation": "Wrap long expressions and split nested calls.",
            "suggested_fix": "Refactor lines >160 chars into multi-line expressions.",
            "risk_level": "low",
            "impact": "Harder reviews and edits.",
            "complexity": "low",
            "estimated_effort": "0.5-1h",
            "expected_benefit": "Improved readability.",
        })

    return findings


def _collect_targets(repo: Dict[str, Any], file_paths: List[str]) -> Tuple[List[ReviewTarget], List[str]]:
    repo_root = _resolve_repo_root(repo.get("index_name") or repo.get("name") or "", repo.get("name") or "")
    targets: List[ReviewTarget] = []
    missing: List[str] = []
    for path in file_paths[:_MAX_FILES]:
        normalized = path.strip().replace("\\", "/")
        if not normalized:
            continue
        target = _read_repo_file(repo_root, normalized)
        if target is None:
            missing.append(normalized)
            continue
        targets.append(target)
    return targets, missing


async def review_files(
    *,
    repo: Dict[str, Any],
    file_paths: List[str],
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    targets, missing = _collect_targets(repo, file_paths)
    snippets = [
        {
            "file": t.path,
            "content": t.content,
        }
        for t in targets
    ]

    ai_payload = await generate_review_payload({
        "prompt": prompt or "",
        "target": "files",
        "repo": {"id": repo.get("id"), "name": repo.get("name")},
        "files": snippets,
    })

    deterministic_findings: List[Dict[str, Any]] = []
    for target in targets:
        deterministic_findings.extend(_extract_code_smells(target))

    findings = ai_payload.get("findings") or []
    if deterministic_findings:
        findings = findings + deterministic_findings

    summary = ai_payload.get("summary") or "Review completed"
    if missing:
        summary = f"{summary} Missing files skipped: {', '.join(missing[:5])}."

    if not findings:
        findings.append({
            "id": str(uuid.uuid4()),
            "severity": "low",
            "file": file_paths[0] if file_paths else "unknown",
            "code_area": "general",
            "finding": "No critical issues detected in the selected scope.",
            "recommendation": "Keep current implementation and add focused tests for high-risk paths.",
            "suggested_fix": "No code change required.",
            "risk_level": "low",
            "impact": "Low immediate risk.",
            "complexity": "low",
            "estimated_effort": "0h",
            "expected_benefit": "Maintains current stability.",
        })

    return {
        "summary": summary,
        "findings": findings,
        "changed_files": [t.path for t in targets],
    }

