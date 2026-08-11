from api.services import supabase_service


def test_get_health_comparison_context_uses_latest_run_and_last_run_with_categories(monkeypatch):
    latest_run = {"id": "run-3", "repository_health": 82}
    prior_with_categories = {"id": "run-2", "repository_health": 90}

    monkeypatch.setattr(
        supabase_service,
        "get_recent_health_runs",
        lambda *args, **kwargs: [latest_run, {"id": "run-empty", "repository_health": 88}, prior_with_categories],
    )

    def fake_score_map(_supabase, *, run_id: str, user_id: str):
        if run_id == "run-2":
            return {"Architecture": 85, "Security": 95}
        return {}

    monkeypatch.setattr(supabase_service, "get_health_category_score_map", fake_score_map)
    monkeypatch.setattr(
        supabase_service,
        "get_health_problem_titles",
        lambda _supabase, *, run_id, user_id: ["risk-a"] if run_id == "run-2" else [],
    )

    run, scores, findings = supabase_service.get_health_comparison_context(
        object(),
        repo_id="repo-1",
        user_id="user-1",
    )

    assert run == latest_run
    assert scores == {"Architecture": 85, "Security": 95}
    assert findings == ["risk-a"]


def test_get_health_comparison_context_returns_none_for_empty_history(monkeypatch):
    monkeypatch.setattr(supabase_service, "get_recent_health_runs", lambda *args, **kwargs: [])

    run, scores, findings = supabase_service.get_health_comparison_context(
        object(),
        repo_id="repo-1",
        user_id="user-1",
    )

    assert run is None
    assert scores is None
    assert findings is None


