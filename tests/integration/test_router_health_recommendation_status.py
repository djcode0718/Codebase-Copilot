from datetime import datetime, timezone
from unittest.mock import patch


def test_recommendation_status_update_keeps_reason_for_legacy_dismissed(client, fake_repo_id):
    captured = {}

    def fake_upsert(
        _supabase,
        *,
        repo_id,
        user_id,
        fingerprint,
        category,
        title,
        status,
        dismissed_reason,
    ):
        captured["repo_id"] = repo_id
        captured["user_id"] = user_id
        captured["fingerprint"] = fingerprint
        captured["status"] = status
        captured["dismissed_reason"] = dismissed_reason
        return {
            "status": "IGNORED",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    with (
        patch("api.routers.health.ensure_repo_access", return_value={"id": fake_repo_id, "user_id": "00000000-0000-0000-0000-000000000001"}),
        patch("api.routers.health.supabase_service.get_latest_health_run", return_value={"id": "run-1"}),
        patch(
            "api.routers.health.supabase_service.get_health_recommendations",
            return_value=[
                {
                    "recommendation_id": "rec-1",
                    "fingerprint": "fp-1",
                    "category": "Security",
                    "title": "Harden auth middleware",
                }
            ],
        ),
        patch("api.routers.health.supabase_service.upsert_health_recommendation_state", side_effect=fake_upsert),
    ):
        response = client.patch(
            f"/api/repo/{fake_repo_id}/health/recommendations/rec-1/status",
            json={"status": "DISMISSED", "reason": "Noise in this repository context"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "IGNORED"
    assert payload["reason"] == "Noise in this repository context"
    assert captured["status"] == "DISMISSED"
    assert captured["dismissed_reason"] == "Noise in this repository context"
