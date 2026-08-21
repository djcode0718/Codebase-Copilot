import os
import shutil
import uuid

from app.config import REPOS_DIR
from api.services.repository_health_engine import RepositoryHealthEngine


def _write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(content)


def _write_batch(files: list) -> None:
    """Write all (path, content) pairs in a single pass — avoids N+1 I/O."""
    for path, content in files:
        _write(path, content)


def test_repository_health_engine_generates_explainable_output():
    repo_name = f"health-fixture-{uuid.uuid4().hex[:8]}"
    repo_path = os.path.join(REPOS_DIR, repo_name)
    os.makedirs(repo_path, exist_ok=True)

    try:
        # Prefetch all fixture definitions, then write in a single batched pass.
        fixture_files = [
            (
                os.path.join(repo_path, 'api', 'routers', 'public.py'),
                """
from fastapi import APIRouter
router = APIRouter()

@router.get('/open')
async def open_endpoint():
    return {'ok': True}
""",
            ),
            (
                os.path.join(repo_path, 'services', 'payments.py'),
                "\n# BACKLOG: add retries\n"
                + "API_KEY = 'hard"
                + "coded_super_secret_123456'\n\n"
                "def charge(items, db):\n"
                "    total = 0\n"
                "    for item in items:\n"
                "        total += db.query(item)\n"
                "    return total\n",
            ),
            (os.path.join(repo_path, 'README.md'), '# Demo\n'),
            (
                os.path.join(repo_path, 'tests', 'test_dummy.py'),
                """
def test_ok():
    assert True
""",
            ),
        ]
        _write_batch(fixture_files)

        engine = RepositoryHealthEngine()
        result = engine.run(
            repo={"id": "repo-1", "name": repo_name, "index_name": repo_name},
            previous_scores={"Security": 95, "Testing": 80},
            previous_findings=["Old risk"],
        )

        assert result["top_level"]["repository_health"] >= 0
        assert len(result["categories"]) == 12
        assert result["findings"]
        assert result["recommendations"]
        assert len(result["recommendations"]) <= 10

        security = next(c for c in result["categories"] if c["category"] == "Security")
        assert security["detected_problems"]
        assert isinstance(security["confidence"], float)
        assert isinstance(security["files_analyzed"], int)
        assert security["checks_performed"]
        assert "severity_breakdown" in security
        assert any("hardcoded" in f["title"].lower() or "secret" in f["title"].lower() for f in result["findings"])
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_testing_analyzer_maps_explorer_service_with_integration_tests():
    repo_name = f"health-testing-map-{uuid.uuid4().hex[:8]}"
    repo_path = os.path.join(REPOS_DIR, repo_name)
    os.makedirs(repo_path, exist_ok=True)

    try:
        fixture_files = [
            (
                os.path.join(repo_path, "api", "services", "repository_explorer_service.py"),
                "def list_directory_tree():\n    return []\n",
            ),
            (
                os.path.join(repo_path, "tests", "integration", "test_router_explorer.py"),
                "def test_explorer_route():\n    assert 'explorer'\n",
            ),
        ]
        _write_batch(fixture_files)

        engine = RepositoryHealthEngine()
        result = engine.run(repo={"id": "repo-2", "name": repo_name, "index_name": repo_name})
        testing = next(c for c in result["categories"] if c["category"] == "Testing")

        assert "Production modules without mapped tests" not in testing["detected_problems"]
        assert "api/services/repository_explorer_service.py" not in testing["affected_files"]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_performance_analyzer_ignores_non_blocking_async_retry_helpers():
    repo_name = f"health-perf-map-{uuid.uuid4().hex[:8]}"
    repo_path = os.path.join(REPOS_DIR, repo_name)
    os.makedirs(repo_path, exist_ok=True)

    try:
        fixture_files = [
            (
                os.path.join(repo_path, "app", "services", "llm_fallback.py"),
                "import threading\n"
                "_EVENT = threading.Event()\n"
                "def wait_retry(seconds: float):\n"
                "    _EVENT.wait(timeout=max(0.0, float(seconds)))\n"
                "async def generate():\n"
                "    return 'ok'\n",
            ),
            (
                os.path.join(repo_path, "tests", "unit", "test_llm_fallback.py"),
                "def test_generate():\n    assert True\n",
            ),
        ]
        _write_batch(fixture_files)

        engine = RepositoryHealthEngine()
        result = engine.run(repo={"id": "repo-3", "name": repo_name, "index_name": repo_name})
        performance = next(c for c in result["categories"] if c["category"] == "Performance")

        assert "Blocking call in async context" not in performance["detected_problems"]
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_repository_health_trend_uses_previous_overall_score_baseline():
    repo_name = f"health-trend-overall-{uuid.uuid4().hex[:8]}"
    repo_path = os.path.join(REPOS_DIR, repo_name)
    os.makedirs(repo_path, exist_ok=True)

    try:
        _write_batch([
            (os.path.join(repo_path, "service.py"), "def ok():\n    return 1\n"),
            (os.path.join(repo_path, "README.md"), "# Trend Fixture\n"),
        ])

        engine = RepositoryHealthEngine()
        first = engine.run(repo={"id": "repo-4", "name": repo_name, "index_name": repo_name})
        current_score = int(first["top_level"]["repository_health"])

        # Intentionally conflicting previous category scores; top-level trend
        # must still follow previous_overall_score.
        second = engine.run(
            repo={"id": "repo-4", "name": repo_name, "index_name": repo_name},
            previous_scores={"Architecture": 100, "Security": 100},
            previous_overall_score=current_score - 8,
        )

        assert second["top_level"]["trend"] == 8
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)


def test_repository_health_category_trends_follow_score_delta():
    repo_name = f"health-trend-category-{uuid.uuid4().hex[:8]}"
    repo_path = os.path.join(REPOS_DIR, repo_name)
    os.makedirs(repo_path, exist_ok=True)

    try:
        _write_batch([
            (os.path.join(repo_path, "app", "main.py"), "def hello():\n    return 'world'\n"),
            (os.path.join(repo_path, "README.md"), "# Category Trend Fixture\n"),
        ])

        engine = RepositoryHealthEngine()
        baseline = engine.run(repo={"id": "repo-5", "name": repo_name, "index_name": repo_name})
        previous_scores = {c["category"]: int(c["score"]) for c in baseline["categories"]}

        follow_up = engine.run(
            repo={"id": "repo-5", "name": repo_name, "index_name": repo_name},
            previous_scores=previous_scores,
            previous_overall_score=int(baseline["top_level"]["repository_health"]),
        )

        deltas = {c["category"]: int(c["trend"]) for c in follow_up["categories"]}
        assert all(delta == 0 for delta in deltas.values())
        assert follow_up["top_level"]["trend"] == 0
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)
