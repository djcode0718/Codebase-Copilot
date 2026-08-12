from api.services import evaluation_center_service


def test_build_history_points_includes_efficiency_metrics():
    rows = [
        {
            "id": "e1",
            "repo_id": "r1",
            "created_at": "2026-08-07T00:00:00+00:00",
            "hit_rate": 0.8,
            "mrr": 0.7,
            "avg_faithfulness": 0.75,
            "avg_relevancy": 0.7,
            "mode_accuracy": 0.8,
            "avg_latency_total": 1100.0,
            "avg_latency_retrieval": 250.0,
            "avg_latency_rerank": 100.0,
            "avg_latency_llm": 750.0,
            "colbert_enabled": False,
            "result_json": {
                "total_queries": 10,
                "efficiency": {
                    "cache_hit_rate": 0.4,
                    "estimated_cost_usd": 0.015,
                },
            },
        }
    ]

    points = evaluation_center_service.build_eval_history_points(rows)

    assert len(points) == 1
    assert points[0]["id"] == "e1"
    assert points[0]["cache_hit_rate"] == 0.4
    assert points[0]["estimated_ai_cost_usd"] == 0.015
    assert points[0]["overall_score"] > 0


def test_build_comparison_payload_uses_summary_deltas():
    current = {
        "id": "new",
        "repo_id": "r1",
        "created_at": "2026-08-07T00:00:00+00:00",
        "hit_rate": 0.9,
        "mrr": 0.8,
        "avg_faithfulness": 0.85,
        "avg_relevancy": 0.8,
        "mode_accuracy": 0.9,
        "avg_latency_total": 950.0,
        "avg_latency_retrieval": 200.0,
        "avg_latency_rerank": 90.0,
        "avg_latency_llm": 660.0,
        "colbert_enabled": False,
        "result_json": {"efficiency": {"estimated_cost_usd": 0.02}},
    }
    baseline = {
        "id": "old",
        "repo_id": "r1",
        "created_at": "2026-08-06T00:00:00+00:00",
        "hit_rate": 0.8,
        "mrr": 0.7,
        "avg_faithfulness": 0.75,
        "avg_relevancy": 0.74,
        "mode_accuracy": 0.85,
        "avg_latency_total": 1200.0,
        "avg_latency_retrieval": 260.0,
        "avg_latency_rerank": 120.0,
        "avg_latency_llm": 820.0,
        "colbert_enabled": False,
        "result_json": {"efficiency": {"estimated_cost_usd": 0.03}},
    }

    comparison = evaluation_center_service.build_comparison_payload(current, baseline)

    assert comparison["baseline_eval_id"] == "old"
    assert comparison["overall_score_delta"] > 0
    assert comparison["hit_rate_delta"] > 0
    assert comparison["latency_delta_ms"] < 0
    assert comparison["estimated_cost_delta_usd"] < 0


def test_evaluation_center_service_uses_use_reranker():
    from api.services import evaluation_center_service as service
    assert isinstance(service.USE_RERANKER, bool)

