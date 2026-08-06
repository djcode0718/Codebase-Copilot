"""Integration tests for repository explorer endpoints."""

from unittest.mock import MagicMock


def _mock_repo_lookup(mock_supabase, repo):
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[repo])
    mock_supabase.table.return_value.select.return_value.eq.return_value = chain


class TestRepositoryExplorerTree:
    def test_tree_success(self, client, mock_supabase, fake_repo, fake_repo_id, monkeypatch):
        _mock_repo_lookup(mock_supabase, fake_repo)

        monkeypatch.setattr(
            "api.routers.explorer.explorer_service.list_directory_tree",
            lambda repo, **kwargs: {
                "repo_root": "C:/repos/demo",
                "path": "",
                "nodes": [
                    {
                        "name": "api",
                        "path": "api",
                        "type": "folder",
                        "has_children": True,
                        "size": 0,
                        "modified_at": None,
                        "language": "folder",
                        "health": "not_analyzed",
                        "ai_indicator": "not_analyzed",
                        "git_status": "",
                        "is_modified": False,
                    }
                ],
                "truncated": False,
                "count": 1,
            },
        )

        resp = client.get(f"/api/repo/{fake_repo_id}/explorer/tree")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["nodes"][0]["path"] == "api"


class TestRepositoryExplorerFile:
    def test_file_not_found(self, client, mock_supabase, fake_repo, fake_repo_id, monkeypatch):
        _mock_repo_lookup(mock_supabase, fake_repo)

        def _missing(*args, **kwargs):
            raise FileNotFoundError("missing")

        monkeypatch.setattr("api.routers.explorer.explorer_service.get_file_details", _missing)

        resp = client.get(f"/api/repo/{fake_repo_id}/explorer/file?path=missing.py")
        assert resp.status_code == 404


class TestRepositoryExplorerReview:
    def test_review_file_success(self, client, mock_supabase, fake_repo, fake_repo_id, monkeypatch):
        _mock_repo_lookup(mock_supabase, fake_repo)

        monkeypatch.setattr(
            "api.routers.explorer.explorer_service.review_single_file",
            lambda repo, **kwargs: {
                "review_id": "r1",
                "scope": "file",
                "overall_score": 87,
                "summary": "Looks good",
                "findings": [],
                "changed_files": [kwargs["relative_path"]],
                "sections": {},
                "generated_at": "2026-01-01T00:00:00+00:00",
            },
        )

        resp = client.post(
            f"/api/repo/{fake_repo_id}/explorer/review/file",
            json={"path": "api/routers/chat.py", "review_type": "security"},
        )
        assert resp.status_code == 200
        assert resp.json()["overall_score"] == 87


class TestRepositoryExplorerTests:
    def test_discover_and_run(self, client, mock_supabase, fake_repo, fake_repo_id, monkeypatch):
        _mock_repo_lookup(mock_supabase, fake_repo)

        monkeypatch.setattr(
            "api.routers.explorer.explorer_service.discover_impacted_tests",
            lambda repo, **kwargs: {"tests": ["tests/unit/test_chat.py"], "count": 1},
        )
        monkeypatch.setattr(
            "api.routers.explorer.explorer_service.run_targeted_tests",
            lambda repo, **kwargs: {
                "status": "passed",
                "tests": kwargs["tests"],
                "passed": 1,
                "failed": 0,
                "duration_seconds": 0.22,
                "coverage": None,
                "output": "1 passed",
            },
        )

        discover = client.post(
            f"/api/repo/{fake_repo_id}/explorer/tests/discover",
            json={"paths": ["api/services/chat_service.py"]},
        )
        assert discover.status_code == 200
        assert discover.json()["count"] == 1

        run = client.post(
            f"/api/repo/{fake_repo_id}/explorer/tests/run",
            json={"tests": ["tests/unit/test_chat.py"], "timeout_seconds": 30},
        )
        assert run.status_code == 200
        assert run.json()["status"] == "passed"


class TestRepositoryExplorerFixApply:
    def test_apply_fix_validation_error(self, client, mock_supabase, fake_repo, fake_repo_id, monkeypatch):
        _mock_repo_lookup(mock_supabase, fake_repo)

        def _raise(*args, **kwargs):
            raise ValueError("Fix rejected: Validation failed")

        monkeypatch.setattr("api.routers.explorer.explorer_service.apply_fix_proposal", _raise)

        resp = client.post(
            f"/api/repo/{fake_repo_id}/explorer/fix/apply",
            json={"fix_id": "abc123", "expected_sha256": "deadbeef", "run_validation": True},
        )
        assert resp.status_code == 400
        assert "rejected" in resp.json()["detail"].lower()
