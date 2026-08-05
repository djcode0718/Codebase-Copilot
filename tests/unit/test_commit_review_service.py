"""
Unit tests for api/services/commit_review_service.py

Covers:
- _repo_root: path resolution with index_name and name fallback
- _run_git: success path and non-zero returncode raises RuntimeError
- _list_changed_files: parses git show output correctly
- _commit_diff: returns raw diff output
- review_commit: delegates to review_files, assembles result
- Negative paths: git failures, missing dirs, empty changed files
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─── _repo_root ──────────────────────────────────────────────────────────────

class TestRepoRoot:
    def test_uses_index_name_when_dir_exists(self, tmp_path):
        repo_dir = tmp_path / "my-index"
        repo_dir.mkdir()

        with patch("api.services.commit_review_service.get_repos_dir", return_value=str(tmp_path)):
            from api.services.commit_review_service import _repo_root
            result = _repo_root({"index_name": "my-index", "name": "other"})

        assert result == str(repo_dir)

    def test_falls_back_to_name_when_index_name_dir_absent(self, tmp_path):
        with patch("api.services.commit_review_service.get_repos_dir", return_value=str(tmp_path)):
            from api.services.commit_review_service import _repo_root
            result = _repo_root({"index_name": "nonexistent", "name": "fallback"})

        assert result == os.path.join(str(tmp_path), "fallback")

    def test_empty_repo_uses_name(self, tmp_path):
        with patch("api.services.commit_review_service.get_repos_dir", return_value=str(tmp_path)):
            from api.services.commit_review_service import _repo_root
            result = _repo_root({"index_name": "does-not-exist-xyz", "name": "myrepo"})

        assert result.endswith("myrepo")


# ─── _run_git ────────────────────────────────────────────────────────────────

class TestRunGit:
    def test_success_returns_stdout(self):
        completed = MagicMock(returncode=0, stdout="abc\n", stderr="")

        with patch("subprocess.run", return_value=completed):
            from api.services.commit_review_service import _run_git
            result = _run_git("/some/dir", ["log", "--oneline"])

        assert result == "abc\n"

    def test_nonzero_returncode_raises(self):
        completed = MagicMock(returncode=1, stdout="", stderr="fatal: not a git repo")

        with patch("subprocess.run", return_value=completed):
            from api.services.commit_review_service import _run_git
            with pytest.raises(RuntimeError, match="fatal: not a git repo"):
                _run_git("/bad/dir", ["log"])

    def test_nonzero_empty_stderr_raises_generic(self):
        completed = MagicMock(returncode=128, stdout="", stderr="")

        with patch("subprocess.run", return_value=completed):
            from api.services.commit_review_service import _run_git
            with pytest.raises(RuntimeError, match="git command failed"):
                _run_git("/dir", ["rev-parse"])


# ─── _list_changed_files ────────────────────────────────────────────────────

class TestListChangedFiles:
    def test_parses_file_list(self):
        git_output = "\napi/main.py\napp/config.py\n"
        with patch("api.services.commit_review_service._run_git", return_value=git_output):
            from api.services.commit_review_service import _list_changed_files
            result = _list_changed_files("/repo", "abc123")

        assert result == ["api/main.py", "app/config.py"]

    def test_empty_output_returns_empty_list(self):
        with patch("api.services.commit_review_service._run_git", return_value=""):
            from api.services.commit_review_service import _list_changed_files
            assert _list_changed_files("/repo", "abc") == []

    def test_normalises_backslashes(self):
        with patch("api.services.commit_review_service._run_git", return_value="a\\b\\c.py\n"):
            from api.services.commit_review_service import _list_changed_files
            result = _list_changed_files("/repo", "abc")

        assert result == ["a/b/c.py"]

    def test_skips_blank_lines(self):
        with patch("api.services.commit_review_service._run_git", return_value="\n\nfile.py\n\n"):
            from api.services.commit_review_service import _list_changed_files
            assert _list_changed_files("/repo", "x") == ["file.py"]


# ─── _commit_diff ────────────────────────────────────────────────────────────

class TestCommitDiff:
    def test_returns_git_output(self):
        with patch("api.services.commit_review_service._run_git", return_value="diff content"):
            from api.services.commit_review_service import _commit_diff
            assert _commit_diff("/repo", "deadbeef") == "diff content"

    def test_git_failure_propagates(self):
        with patch("api.services.commit_review_service._run_git", side_effect=RuntimeError("fail")):
            from api.services.commit_review_service import _commit_diff
            with pytest.raises(RuntimeError):
                _commit_diff("/repo", "bad")


# ─── review_commit ──────────────────────────────────────────────────────────

class TestReviewCommit:
    @pytest.fixture()
    def repo(self):
        return {"index_name": "myrepo", "name": "myrepo", "id": "r-1"}

    @pytest.mark.asyncio
    async def test_returns_expected_structure(self, repo):
        files = ["api/main.py", "app/config.py"]
        review_result = {
            "summary": "All good",
            "findings": [{"id": "f1", "severity": "low", "finding": "minor issue"}],
            "changed_files": files,
        }

        with (
            patch("api.services.commit_review_service._repo_root", return_value="/repo"),
            patch("api.services.commit_review_service._list_changed_files", return_value=files),
            patch("api.services.commit_review_service._commit_diff", return_value="diff text"),
            patch(
                "api.services.commit_review_service.review_files",
                new_callable=AsyncMock,
                return_value=review_result,
            ),
        ):
            from api.services.commit_review_service import review_commit
            result = await review_commit(repo=repo, commit_hash="abc123")

        assert result["commit_hash"] == "abc123"
        assert "abc123"[:12] in result["summary"]
        assert result["findings"] == review_result["findings"]
        assert result["changed_files"] == files
        assert result["diff"] == "diff text"

    @pytest.mark.asyncio
    async def test_limits_files_to_20(self, repo):
        files = [f"file{i}.py" for i in range(30)]

        with (
            patch("api.services.commit_review_service._repo_root", return_value="/r"),
            patch("api.services.commit_review_service._list_changed_files", return_value=files),
            patch("api.services.commit_review_service._commit_diff", return_value=""),
            patch(
                "api.services.commit_review_service.review_files",
                new_callable=AsyncMock,
                return_value={"summary": "ok", "findings": [], "changed_files": files[:20]},
            ) as mock_rf,
        ):
            from api.services.commit_review_service import review_commit
            result = await review_commit(repo=repo, commit_hash="x")

        called_paths = mock_rf.call_args.kwargs["file_paths"]
        assert len(called_paths) == 20
        assert len(result["changed_files"]) == 20

    @pytest.mark.asyncio
    async def test_git_error_propagates(self, repo):
        with (
            patch("api.services.commit_review_service._repo_root", return_value="/r"),
            patch(
                "api.services.commit_review_service._list_changed_files",
                side_effect=RuntimeError("fatal: bad object"),
            ),
        ):
            from api.services.commit_review_service import review_commit
            with pytest.raises(RuntimeError, match="bad object"):
                await review_commit(repo=repo, commit_hash="bad")

    @pytest.mark.asyncio
    async def test_passes_prompt_to_review_files(self, repo):
        with (
            patch("api.services.commit_review_service._repo_root", return_value="/r"),
            patch("api.services.commit_review_service._list_changed_files", return_value=["f.py"]),
            patch("api.services.commit_review_service._commit_diff", return_value=""),
            patch(
                "api.services.commit_review_service.review_files",
                new_callable=AsyncMock,
                return_value={"summary": "ok", "findings": [], "changed_files": ["f.py"]},
            ) as mock_rf,
        ):
            from api.services.commit_review_service import review_commit
            await review_commit(repo=repo, commit_hash="abc", prompt="focus on security")

        assert mock_rf.call_args.kwargs["prompt"] == "focus on security"
