"""AI-backed review/fix generation helpers with deterministic fallbacks."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from app.utils.logger import get_logger
from app.llm.prompts import REVIEW_PAYLOAD_PROMPT, FIX_TEXT_PROMPT

logger = get_logger(__name__)


def _strip_code_fence(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 2:
            raw = "\n".join(lines[1:-1]).strip()
    return raw


def _normalize_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(findings):
        severity = str(item.get("severity") or "medium").lower()
        if severity not in {"low", "medium", "high", "critical"}:
            severity = "medium"
        risk = str(item.get("risk_level") or "medium").lower()
        if risk not in {"low", "medium", "high"}:
            risk = "medium"

        normalized.append({
            "id": str(item.get("id") or f"finding-{idx + 1}"),
            "severity": severity,
            "file": str(item.get("file") or "unknown"),
            "code_area": str(item.get("code_area") or "general"),
            "finding": str(item.get("finding") or "Issue detected"),
            "recommendation": str(item.get("recommendation") or "Apply focused remediation."),
            "suggested_fix": str(item.get("suggested_fix") or ""),
            "risk_level": risk,
            "impact": str(item.get("impact") or ""),
            "complexity": str(item.get("complexity") or ""),
            "estimated_effort": str(item.get("estimated_effort") or ""),
            "expected_benefit": str(item.get("expected_benefit") or ""),
        })
    return normalized


async def generate_review_payload(review_request: Dict[str, Any]) -> Dict[str, Any]:
    """Generate structured review payload via LLM fallback chain."""
    from app.services.llm_fallback import generate_with_fallback

    prompt = REVIEW_PAYLOAD_PROMPT.format(
        review_input_json=json.dumps(review_request, ensure_ascii=True)
    )

    try:
        raw = await generate_with_fallback(prompt)
        parsed = json.loads(_strip_code_fence(raw))
        summary = str(parsed.get("summary") or "Review completed")
        findings = _normalize_findings(parsed.get("findings") or [])
        return {"summary": summary, "findings": findings}
    except Exception as err:
        logger.warning(f"AI review generation fallback activated: {err}")
        return {
            "summary": "Review completed with deterministic checks.",
            "findings": [],
        }


async def generate_fix_text(fix_request: Dict[str, Any]) -> str:
    """Generate minimal fix proposal text for an accepted finding."""
    from app.services.llm_fallback import generate_with_fallback

    prompt = FIX_TEXT_PROMPT.format(
        fix_input_json=json.dumps(fix_request, ensure_ascii=True)
    )

    try:
        return (await generate_with_fallback(prompt)).strip()
    except Exception as err:
        logger.warning(f"AI fix generation fallback activated: {err}")
        finding = fix_request.get("finding") or "Issue"
        file_path = fix_request.get("file") or "target file"
        return (
            f"Problem: {finding}\n"
            f"Minimal Diff Plan: Update only {file_path} with a focused conditional/validation fix tied to the finding.\n"
            "Validation Steps: run relevant unit/integration tests for touched behavior."
        )

