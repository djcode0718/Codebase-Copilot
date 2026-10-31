"""Smoke tests for api/services/pull_request_review_service.py"""
from __future__ import annotations
import pytest


def test_pull_request_review_service_module_importable():
    """Verify the pull_request_review_service module can be imported."""
    import api.services.pull_request_review_service as svc
    assert svc is not None


def test_truncate_diff_under_limit():
    from api.services.pull_request_review_service import _truncate_diff
    diff = "diff --git a/foo.py b/foo.py\n+hello = 'world'\n"
    res = _truncate_diff(diff, 40000)
    assert res == diff
    assert "[TRUNCATED FOR REVIEW]" not in res


def test_truncate_diff_oversized_newline_snapped_with_sentinel():
    from api.services.pull_request_review_service import _truncate_diff
    lines = [f"+line_{i} " + ("x" * 80) + "\n" for i in range(50)]
    diff = "".join(lines)
    assert len(diff) > 4000

    res = _truncate_diff(diff, 2000)
    assert "[TRUNCATED FOR REVIEW" in res
    body = res.split("\n\n# --- [TRUNCATED FOR REVIEW")[0]
    assert len(body) <= 2000
    assert body.endswith("\n") or body.endswith("x")


@pytest.mark.asyncio
async def test_review_pull_request_diff_bounded_by_provider_budget():
    from unittest.mock import AsyncMock, patch
    from api.services.pull_request_review_service import review_pull_request

    huge_diff = "diff --git a/test.py b/test.py\n" + ("+test line\n" * 5000)  # >50,000 chars
    mock_payload = {"summary": "PR reviewed", "findings": []}
    mock_files_review = {"summary": "Files reviewed", "findings": []}

    repo = {"id": "repo-123", "name": "test-repo"}
    with patch("api.services.pull_request_review_service.review_files", new_callable=AsyncMock, return_value=mock_files_review) as mock_rf, \
         patch("api.services.pull_request_review_service.generate_review_payload", new_callable=AsyncMock, return_value=mock_payload) as mock_grp:

        res = await review_pull_request(
            repo=repo,
            changed_files=["test.py"],
            diff=huge_diff,
            provider="ollama",
        )
        assert res["summary"] == "PR reviewed"
        mock_rf.assert_called_once()
        assert mock_rf.call_args[1]["provider"] == "ollama"

        mock_grp.assert_called_once()
        passed_diff = mock_grp.call_args[0][0]["diff"]
        assert len(passed_diff) < len(huge_diff)
        assert "[TRUNCATED FOR REVIEW" in passed_diff
