import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _repo(fake_repo_id: str, fake_user_id: str):
    return {
        "id": fake_repo_id,
        "user_id": fake_user_id,
        "name": "test-repo",
        "index_name": "test-repo",
        "status": "ready",
    }


def test_review_file_endpoint_success(client, fake_repo_id, fake_user_id):
    with (
        patch("api.routers.reviews.supabase_service.get_repo", return_value=_repo(fake_repo_id, fake_user_id)),
        patch("api.routers.reviews.review_files") as mock_review_files,
        patch("api.routers.reviews.store_review") as mock_store_review,
    ):
        mock_review_files.return_value = {
            "summary": "ok",
            "findings": [{
                "id": "f1",
                "severity": "low",
                "file": "api/routers/chat.py",
                "code_area": "general",
                "finding": "sample",
                "recommendation": "sample",
                "suggested_fix": "sample",
                "risk_level": "low",
                "impact": "",
                "complexity": "",
                "estimated_effort": "",
                "expected_benefit": "",
            }],
            "changed_files": ["api/routers/chat.py"],
        }
        mock_store_review.return_value = {
            "id": "r1",
            "repo_id": fake_repo_id,
            "target_type": "file",
            "status": "completed",
            "summary": "ok",
            "findings": mock_review_files.return_value["findings"],
            "changed_files": ["api/routers/chat.py"],
            "created_at": "2026-08-05T00:00:00+00:00",
        }

        resp = client.post("/api/reviews/file", json={"repo_id": fake_repo_id, "filename": "api/routers/chat.py"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["review_id"] == "r1"
    assert data["target_type"] == "file"


def test_review_files_requires_files(client, fake_repo_id, fake_user_id):
    with patch("api.routers.reviews.supabase_service.get_repo", return_value=_repo(fake_repo_id, fake_user_id)):
        resp = client.post("/api/reviews/files", json={"repo_id": fake_repo_id, "files": []})
    assert resp.status_code == 400


def test_list_and_get_review(client, fake_repo_id, fake_user_id):
    row = {
        "id": "r2",
        "repo_id": fake_repo_id,
        "target_type": "files",
        "status": "completed",
        "summary": "multi",
        "findings": [],
        "changed_files": ["api/services/chat_service.py"],
        "created_at": "2026-08-05T00:00:00+00:00",
    }
    with (
        patch("api.routers.reviews.supabase_service.get_repo", return_value=_repo(fake_repo_id, fake_user_id)),
        patch("api.routers.reviews.list_reviews", return_value=[row]),
        patch("api.routers.reviews.get_review", return_value=row),
    ):
        list_resp = client.get(f"/api/reviews?repo_id={fake_repo_id}")
        get_resp = client.get("/api/reviews/r2")

    assert list_resp.status_code == 200
    assert list_resp.json()["items"][0]["review_id"] == "r2"
    assert get_resp.status_code == 200
    assert get_resp.json()["review_id"] == "r2"


def test_generate_fix_and_delete(client, fake_repo_id, fake_user_id):
    row = {
        "id": "r3",
        "repo_id": fake_repo_id,
        "target_type": "file",
        "status": "completed",
        "summary": "single",
        "findings": [{
            "id": "f3",
            "finding": "issue",
            "file": "api/services/chat_service.py",
            "code_area": "streaming",
            "recommendation": "fix",
        }],
        "changed_files": ["api/services/chat_service.py"],
    }
    with (
        patch("api.routers.reviews.supabase_service.get_repo", return_value=_repo(fake_repo_id, fake_user_id)),
        patch("api.routers.reviews.get_review", return_value=row),
        patch("api.routers.reviews.generate_fix_text", return_value="Problem: issue\nMinimal Diff Plan: ..."),
        patch("api.routers.reviews.delete_review", return_value=True),
    ):
        fix_resp = client.post("/api/reviews/fix", json={"review_id": "r3", "finding_id": "f3"})
        del_resp = client.delete("/api/reviews/r3")

    assert fix_resp.status_code == 200
    assert "Minimal Diff Plan" in fix_resp.json()["suggested_fix"]
    assert del_resp.status_code == 200

