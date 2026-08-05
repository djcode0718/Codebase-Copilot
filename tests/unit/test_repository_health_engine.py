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
                "\n# TODO: add retries\n"
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
        assert any("hardcoded" in f["title"].lower() or "secret" in f["title"].lower() for f in result["findings"])
    finally:
        shutil.rmtree(repo_path, ignore_errors=True)
