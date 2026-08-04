"""Pull-request style review service for diff/file scoped analysis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.services.review_service import review_files
from api.services.review_suggestion_service import generate_review_payload


async def review_pull_request(
    *,
    repo: Dict[str, Any],
    changed_files: List[str],
    diff: str,
    prompt: Optional[str] = None,
) -> Dict[str, Any]:
    file_review = await review_files(repo=repo, file_paths=changed_files, prompt=prompt)

    ai_payload = await generate_review_payload({
        "prompt": prompt or "",
        "target": "pr",
        "repo": {"id": repo.get("id"), "name": repo.get("name")},
        "changed_files": changed_files[:25],
        "diff": (diff or "")[:40000],
    })

    findings = (ai_payload.get("findings") or []) + (file_review.get("findings") or [])
    return {
        "summary": ai_payload.get("summary") or file_review.get("summary") or "PR review completed.",
        "findings": findings,
        "changed_files": changed_files[:25],
    }

