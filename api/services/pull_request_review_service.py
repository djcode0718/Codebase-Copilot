"""Pull-request style review service for diff/file scoped analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.services.review_service import (
    _TRUNCATION_SENTINEL,
    _resolve_review_budget,
    review_files,
)
from api.services.review_suggestion_service import generate_review_payload


def _truncate_diff(diff_text: str, max_chars: int) -> str:
    raw = diff_text or ""
    if len(raw) <= max_chars:
        return raw
    cut = raw[:max_chars]
    last_nl = cut.rfind("\n")
    if last_nl > 0:
        cut = cut[:last_nl]
    return cut + _TRUNCATION_SENTINEL


async def review_pull_request(
    *,
    repo: Dict[str, Any],
    changed_files: List[str],
    diff: str,
    prompt: Optional[str] = None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    file_review = await review_files(repo=repo, file_paths=changed_files, prompt=prompt, provider=provider)

    single_limit, _, _ = _resolve_review_budget(1, provider=provider)
    bounded_diff = _truncate_diff(diff, single_limit)

    ai_payload = await generate_review_payload({
        "prompt": prompt or "",
        "target": "pr",
        "repo": {"id": repo.get("id"), "name": repo.get("name")},
        "changed_files": changed_files[:25],
        "diff": bounded_diff,
    })

    findings = (ai_payload.get("findings") or []) + (file_review.get("findings") or [])
    return {
        "summary": ai_payload.get("summary") or file_review.get("summary") or "PR review completed.",
        "findings": findings,
        "changed_files": changed_files[:25],
    }

