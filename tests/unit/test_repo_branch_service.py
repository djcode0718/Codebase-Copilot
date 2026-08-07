from __future__ import annotations

from api.services import repo_branch_service


def test_normalize_branch_name_handles_origin_prefix() -> None:
    assert repo_branch_service._normalize_branch_name("origin/main") == "main"
    assert repo_branch_service._normalize_branch_name("refs/remotes/origin/feature/payments") == "feature/payments"


def test_list_branches_returns_normalized_remote_names(monkeypatch) -> None:
    monkeypatch.setattr(repo_branch_service, "_repo_root", lambda _repo: "C:/tmp/repo")

    def _fake_safe_run_git(_repo_root: str, args: list[str], fallback: str = "") -> str:
        cmd = " ".join(args)
        if "symbolic-ref refs/remotes/origin/HEAD" in cmd:
            return "refs/remotes/origin/main"
        if "rev-parse --abbrev-ref HEAD" in cmd:
            return "main"
        if "refs/heads" in cmd:
            return "main\nfeature/auth"
        if "refs/remotes/origin" in cmd:
            return "origin/main\norigin/feature/auth"
        return fallback

    monkeypatch.setattr(repo_branch_service, "_safe_run_git", _fake_safe_run_git)

    result = repo_branch_service.list_branches({"id": "repo-1"})

    assert "main" in result["remote_branches"]
    assert "feature/auth" in result["remote_branches"]
    assert "origin/main" not in result["remote_branches"]
