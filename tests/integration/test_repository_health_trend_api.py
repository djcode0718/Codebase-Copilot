from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from api.routers import health as health_router


def test_health_run_trend_updates_across_runs(client, fake_repo_id):
    health_router._TRANSIENT_HEALTH_RUNS.clear()
    base_time = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
    runs: list[dict] = []
    category_rows: dict[str, list[dict]] = {}

    score_sequence = [85, 90, 82]
    category_sequence = [
        {"Architecture": 80, "Security": 90},
        {"Architecture": 85, "Security": 95},
        {"Architecture": 75, "Security": 89},
    ]
    run_counter = {"value": 0}

    def fake_get_health_comparison_context(_supabase, *, repo_id: str, user_id: str, lookback_runs: int = 20):
        if not runs:
            return None, None, None
        latest = sorted(runs, key=lambda r: r["created_at"], reverse=True)[0]
        sorted_runs = sorted(runs, key=lambda r: r["created_at"], reverse=True)
        for run in sorted_runs:
            rows = category_rows.get(run["id"], [])
            if rows:
                return latest, {r["category"]: int(r["score"]) for r in rows}, []
        return latest, None, None

    def fake_engine_run(*, repo, previous_scores=None, previous_findings=None, previous_overall_score=None):
        idx = run_counter["value"]
        run_counter["value"] += 1
        repo_score = score_sequence[idx]
        categories = []
        for name, score in category_sequence[idx].items():
            prior = (previous_scores or {}).get(name)
            cat_trend = score - int(prior) if prior is not None else 0
            categories.append(
                {
                    "category": name,
                    "score": score,
                    "grade": "A" if score >= 90 else "B",
                    "trend": cat_trend,
                    "explanation": f"{name} baseline",
                    "detected_problems": [],
                    "positive_findings": [],
                    "recommendations": [],
                    "affected_files": [],
                    "affected_modules": [],
                }
            )

        if previous_overall_score is None:
            trend = 0
        else:
            trend = repo_score - int(previous_overall_score)

        return {
            "top_level": {
                "repository_health": repo_score,
                "grade": "B",
                "status": "Strong",
                "trend": trend,
                "last_analysis": base_time + timedelta(seconds=idx),
                "repository_size": "Small",
                "language_detection": ["Python"],
                "framework_detection": [],
            },
            "categories": categories,
            "findings": [],
            "recommendations": [],
            "executive_summary": "summary",
            "strengths": [],
            "weaknesses": [],
            "critical_risks": [],
            "architecture_risks": [],
            "security_risks": [],
            "performance_risks": [],
            "recommended_sprint": [],
            "improved_categories": [c["category"] for c in categories if c["trend"] > 0],
            "declining_categories": [c["category"] for c in categories if c["trend"] < 0],
            "new_risks": [],
            "resolved_risks": [],
            "benchmark": {},
        }

    def fake_insert_health_run(
        _supabase,
        *,
        repo_id: str,
        user_id: str,
        top_level,
        executive_summary,
        strengths,
        weaknesses,
        critical_risks,
        architecture_risks,
        security_risks,
        performance_risks,
        recommended_sprint,
        improved_categories,
        declining_categories,
        new_risks,
        resolved_risks,
        benchmark,
    ):
        run_id = f"run-{len(runs) + 1}"
        created_at = (base_time + timedelta(seconds=len(runs))).isoformat()
        record = {
            "id": run_id,
            "repo_id": repo_id,
            "user_id": user_id,
            "repository_health": int(top_level["repository_health"]),
            "grade": top_level["grade"],
            "status": top_level["status"],
            "trend": int(top_level["trend"]),
            "repository_size": top_level["repository_size"],
            "language_detection": top_level["language_detection"],
            "framework_detection": top_level["framework_detection"],
            "executive_summary": executive_summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "critical_risks": critical_risks,
            "architecture_risks": architecture_risks,
            "security_risks": security_risks,
            "performance_risks": performance_risks,
            "recommended_sprint": recommended_sprint,
            "improved_categories": improved_categories,
            "declining_categories": declining_categories,
            "new_risks": new_risks,
            "resolved_risks": resolved_risks,
            "benchmark": benchmark,
            "created_at": created_at,
        }
        runs.append(record)
        return record

    def fake_insert_health_category_scores(_supabase, *, run_id: str, repo_id: str, user_id: str, categories):
        category_rows[run_id] = [
            {
                **category,
                "id": f"{run_id}-{index}",
                "run_id": run_id,
                "repo_id": repo_id,
                "user_id": user_id,
                "created_at": (base_time + timedelta(seconds=len(runs))).isoformat(),
            }
            for index, category in enumerate(categories, start=1)
        ]

    def fake_get_health_run_by_id(_supabase, *, run_id: str, user_id: str):
        return next((r for r in runs if r["id"] == run_id and r["user_id"] == user_id), None)

    def fake_get_latest_health_run(_supabase, *, repo_id: str, user_id: str):
        filtered = [r for r in runs if r["repo_id"] == repo_id and r["user_id"] == user_id]
        if not filtered:
            return None
        return sorted(filtered, key=lambda r: r["created_at"], reverse=True)[0]

    def fake_get_health_category_scores(_supabase, *, run_id: str, user_id: str):
        return [r for r in category_rows.get(run_id, []) if r["user_id"] == user_id]

    def fake_get_health_category_score_map(_supabase, *, run_id: str, user_id: str):
        rows = fake_get_health_category_scores(_supabase, run_id=run_id, user_id=user_id)
        return {row["category"]: int(row["score"]) for row in rows}

    def fake_get_health_history(_supabase, *, repo_id: str, user_id: str, days: int = 30, limit: int = 30):
        filtered = [r for r in runs if r["repo_id"] == repo_id and r["user_id"] == user_id]
        return sorted(filtered, key=lambda r: r["created_at"], reverse=True)[:limit]

    with (
        patch("api.routers.health.ensure_repo_access", return_value={"id": fake_repo_id, "user_id": "00000000-0000-0000-0000-000000000001", "index_name": "demo"}),
        patch.object(health_router.engine, "run", side_effect=fake_engine_run),
        patch("api.routers.health.supabase_service.get_health_comparison_context", side_effect=fake_get_health_comparison_context),
        patch("api.routers.health.supabase_service.insert_health_run", side_effect=fake_insert_health_run),
        patch("api.routers.health.supabase_service.insert_health_category_scores", side_effect=fake_insert_health_category_scores),
        patch("api.routers.health.supabase_service.insert_health_findings", return_value=None),
        patch("api.routers.health.supabase_service.insert_health_recommendations", return_value=None),
        patch("api.routers.health.supabase_service.get_health_run_by_id", side_effect=fake_get_health_run_by_id),
        patch("api.routers.health.supabase_service.get_latest_health_run", side_effect=fake_get_latest_health_run),
        patch("api.routers.health.supabase_service.get_health_category_scores", side_effect=fake_get_health_category_scores),
        patch("api.routers.health.supabase_service.get_health_findings", return_value=[]),
        patch("api.routers.health.supabase_service.get_health_recommendations", return_value=[]),
        patch("api.routers.health.supabase_service.get_health_category_score_map", side_effect=fake_get_health_category_score_map),
        patch("api.routers.health.supabase_service.get_health_history", side_effect=fake_get_health_history),
    ):
        first = client.post(f"/api/repo/{fake_repo_id}/health/run")
        second = client.post(f"/api/repo/{fake_repo_id}/health/run")
        third = client.post(f"/api/repo/{fake_repo_id}/health/run")

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 200

        first_body = first.json()
        second_body = second.json()
        third_body = third.json()

        assert first_body["top_level"]["repository_health"] == 85
        assert first_body["top_level"]["trend"] == 0

        assert second_body["top_level"]["repository_health"] == 90
        assert second_body["top_level"]["trend"] == 5
        assert {c["category"]: c["trend"] for c in second_body["categories"]} == {
            "Architecture": 5,
            "Security": 5,
        }

        assert third_body["top_level"]["repository_health"] == 82
        assert third_body["top_level"]["trend"] == -8
        assert {c["category"]: c["trend"] for c in third_body["categories"]} == {
            "Architecture": -10,
            "Security": -6,
        }

        latest = client.get(f"/api/repo/{fake_repo_id}/health/latest")
        assert latest.status_code == 200
        assert latest.json()["latest"]["top_level"]["trend"] == -8

        history = client.get(f"/api/repo/{fake_repo_id}/health/history?days=30&limit=30")
        assert history.status_code == 200
        points = history.json()["points"]
        assert [p["repository_health"] for p in points] == [82, 90, 85]


def test_health_run_trend_updates_in_transient_mode_when_tables_missing(client, fake_repo_id):
    health_router._TRANSIENT_HEALTH_RUNS.clear()

    score_sequence = [85, 90, 82]
    category_sequence = [
        {"Architecture": 80, "Security": 90},
        {"Architecture": 85, "Security": 95},
        {"Architecture": 75, "Security": 89},
    ]
    run_counter = {"value": 0}

    def fake_engine_run(*, repo, previous_scores=None, previous_findings=None, previous_overall_score=None):
        idx = run_counter["value"]
        run_counter["value"] += 1
        repo_score = score_sequence[idx]

        categories = []
        for name, score in category_sequence[idx].items():
            prior = (previous_scores or {}).get(name)
            categories.append(
                {
                    "category": name,
                    "score": score,
                    "grade": "A" if score >= 90 else "B",
                    "trend": score - int(prior) if prior is not None else 0,
                    "explanation": "transient",
                    "detected_problems": [],
                    "positive_findings": [],
                    "recommendations": [],
                    "affected_files": [],
                    "affected_modules": [],
                }
            )

        trend = 0 if previous_overall_score is None else repo_score - int(previous_overall_score)

        return {
            "top_level": {
                "repository_health": repo_score,
                "grade": "B",
                "status": "Strong",
                "trend": trend,
                "last_analysis": datetime.now(timezone.utc),
                "repository_size": "Small",
                "language_detection": ["Python"],
                "framework_detection": [],
            },
            "categories": categories,
            "findings": [],
            "recommendations": [],
            "executive_summary": "summary",
            "strengths": [],
            "weaknesses": [],
            "critical_risks": [],
            "architecture_risks": [],
            "security_risks": [],
            "performance_risks": [],
            "recommended_sprint": [],
            "improved_categories": [c["category"] for c in categories if c["trend"] > 0],
            "declining_categories": [c["category"] for c in categories if c["trend"] < 0],
            "new_risks": [],
            "resolved_risks": [],
            "benchmark": {},
        }

    with (
        patch("api.routers.health.ensure_repo_access", return_value={"id": fake_repo_id, "user_id": "00000000-0000-0000-0000-000000000001", "index_name": "demo"}),
        patch.object(health_router.engine, "run", side_effect=fake_engine_run),
        patch("api.routers.health.supabase_service.get_health_comparison_context", return_value=(None, None, None)),
        patch("api.routers.health.supabase_service.insert_health_run", side_effect=Exception("PGRST205: Could not find the table 'public.repository_health_runs' in the schema cache")),
        patch("api.routers.health.supabase_service.get_latest_health_run", return_value=None),
        patch("api.routers.health.supabase_service.get_health_history", return_value=[]),
    ):
        first = client.post(f"/api/repo/{fake_repo_id}/health/run")
        second = client.post(f"/api/repo/{fake_repo_id}/health/run")
        third = client.post(f"/api/repo/{fake_repo_id}/health/run")

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 200

        assert first.json()["top_level"]["trend"] == 0
        assert second.json()["top_level"]["trend"] == 5
        assert third.json()["top_level"]["trend"] == -8

        latest = client.get(f"/api/repo/{fake_repo_id}/health/latest")
        assert latest.status_code == 200
        latest_payload = latest.json()["latest"]
        assert latest_payload is not None
        assert latest_payload["top_level"]["trend"] == -8
        assert str(latest_payload["run_id"]).startswith("transient-")

        history = client.get(f"/api/repo/{fake_repo_id}/health/history?days=30&limit=30")
        assert history.status_code == 200
        points = history.json()["points"]
        assert [p["repository_health"] for p in points] == [82, 90, 85]


