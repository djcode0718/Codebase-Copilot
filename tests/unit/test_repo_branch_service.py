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


def test_resolve_compare_ref_prefers_local_then_remote(monkeypatch) -> None:
    def _fake_safe_run_git(_repo_root: str, args: list[str], fallback: str = "") -> str:
        cmd = " ".join(args)
        if "show-ref --verify refs/heads/main" in cmd:
            return "local-main-ref"
        if "show-ref --verify refs/heads/feature/x" in cmd:
            return ""
        if "show-ref --verify refs/remotes/origin/feature/x" in cmd:
            return "remote-feature-ref"
        return fallback

    monkeypatch.setattr(repo_branch_service, "_safe_run_git", _fake_safe_run_git)

    assert repo_branch_service._resolve_compare_ref("C:/tmp/repo", "main") == "main"
    assert repo_branch_service._resolve_compare_ref("C:/tmp/repo", "feature/x") == "origin/feature/x"


def test_compare_branches_uses_resolved_refs_and_counts_files(monkeypatch) -> None:
    monkeypatch.setattr(repo_branch_service, "_repo_root", lambda _repo: "C:/tmp/repo")
    monkeypatch.setattr(repo_branch_service, "_resolve_compare_ref", lambda _root, name: f"origin/{name}")

    def _fake_run_git(_repo_root: str, args: list[str]) -> str:
        cmd = " ".join(args)
        if cmd == "fetch --all --prune":
            return ""
        if cmd == "diff --name-only --no-renames origin/main origin/feature/x":
            return "api/services/repo_branch_service.py\nfrontend/components/repo/BranchWorkspacePanel.tsx"
        raise AssertionError(f"Unexpected git command: {cmd}")

    monkeypatch.setattr(repo_branch_service, "_run_git", _fake_run_git)

    result = repo_branch_service.compare_branches({"id": "repo-1"}, base_branch="main", target_branch="feature/x")

    assert result["changed_files"] == 2
    assert "api/services/repo_branch_service.py" in result["sample_changed_files"]
