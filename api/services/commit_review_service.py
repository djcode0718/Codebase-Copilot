"""Commit review service using repository-local git data."""

from __future__ import annotations

import subprocess
from typing import Any, Dict, List, Optional

from api.services.review_service import review_files
from app.config import get_repos_dir
import os


def _repo_root(repo: Dict[str, Any]) -> str:
    repos_dir = get_repos_dir()
    primary = os.path.join(repos_dir, repo.get("index_name") or "")
    if os.path.isdir(primary):
        return primary
    return os.path.join(repos_dir, repo.get("name") or "")


def _run_git(repo_root: str, args: List[str]) -> str:
    completed = subprocess.run(
        ["git", "--no-pager", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")
    return completed.stdout


def _list_changed_files(repo_root: str, commit_hash: str) -> List[str]:
    out = _run_git(repo_root, ["show", "--name-only", "--pretty=format:", commit_hash])
    files = [line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()]
    return files


def _commit_diff(repo_root: str, commit_hash: str) -> str:
    return _run_git(repo_root, ["show", "--unified=2", commit_hash])


async def review_commit(*, repo: Dict[str, Any], commit_hash: str, prompt: Optional[str] = None) -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    changed_files = _list_changed_files(repo_root, commit_hash)
    scoped = changed_files[:20]
    files_review = await review_files(repo=repo, file_paths=scoped, prompt=prompt)
    return {
        "summary": f"Commit review completed for {commit_hash[:12]}. {files_review['summary']}",
        "findings": files_review["findings"],
        "changed_files": scoped,
        "commit_hash": commit_hash,
        "diff": _commit_diff(repo_root, commit_hash)[:40000],
    }

