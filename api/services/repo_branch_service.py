from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from app.config import REPOS_DIR
from app.utils.git_auth import get_git_auth_token
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _repo_root(repo: Dict[str, Any]) -> str:
    for candidate in (repo.get("index_name"), repo.get("name")):
        if not candidate:
            continue
        root = os.path.join(REPOS_DIR, str(candidate))
        if os.path.isdir(root):
            return root
    raise FileNotFoundError("Local repository workspace is unavailable. Re-index or refresh the repository.")


def _run_git(repo_root: str, args: List[str]) -> str:
    token = get_git_auth_token()
    cmd = ["git", "--no-pager"]
    if token:
        safe_token = quote(token, safe="")
        cmd += [
            "-c",
            f"url.https://x-access-token:{safe_token}@github.com/.insteadof=https://github.com/",
        ]
    cmd.extend(args)

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"

    completed = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "git command failed")
    return completed.stdout.strip()


def _safe_run_git(repo_root: str, args: List[str], fallback: str = "") -> str:
    try:
        return _run_git(repo_root, args)
    except Exception:
        return fallback


def _branch_ref_exists(repo_root: str, ref_name: str) -> bool:
    return bool(_safe_run_git(repo_root, ["show-ref", "--verify", ref_name], ""))


def _resolve_compare_ref(repo_root: str, branch: str) -> str:
    """Resolve a branch to the best available ref for compare operations."""
    normalized = _normalize_branch_name(branch)
    if not normalized:
        raise RuntimeError("Branch name is required.")

    if _branch_ref_exists(repo_root, f"refs/heads/{normalized}"):
        return normalized
    if _branch_ref_exists(repo_root, f"refs/remotes/origin/{normalized}"):
        return f"origin/{normalized}"

    # Last resort: allow explicit revs that git can parse.
    parsed = _safe_run_git(repo_root, ["rev-parse", "--verify", normalized], "")
    if parsed:
        return normalized

    raise RuntimeError(f"Branch '{normalized}' was not found locally or on origin.")


def _detect_default_branch(repo_root: str) -> str:
    head_ref = _safe_run_git(repo_root, ["symbolic-ref", "refs/remotes/origin/HEAD"], "")
    if head_ref.startswith("refs/remotes/origin/"):
        return head_ref.replace("refs/remotes/origin/", "", 1)

    local_heads = _safe_run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"], "")
    local_set = {line.strip() for line in local_heads.splitlines() if line.strip()}
    if "main" in local_set:
        return "main"
    if "master" in local_set:
        return "master"

    return _safe_run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], "main") or "main"


def _normalize_branch_name(name: str) -> str:
    normalized = name.strip().replace("refs/heads/", "").replace("refs/remotes/origin/", "")
    if normalized.startswith("origin/"):
        normalized = normalized[len("origin/") :]
    return normalized


def get_current_branch(repo: Dict[str, Any]) -> str:
    repo_root = _repo_root(repo)
    return _safe_run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], "unknown")


def list_branches(repo: Dict[str, Any], query: str = "") -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    default_branch = _detect_default_branch(repo_root)
    current_branch = _safe_run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], default_branch)

    local_raw = _safe_run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"], "")
    remote_raw = _safe_run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/remotes/origin"], "")

    local_branches = [_normalize_branch_name(line) for line in local_raw.splitlines() if line.strip()]
    remote_branches = [
        _normalize_branch_name(line)
        for line in remote_raw.splitlines()
        if line.strip() and not line.strip().endswith("/HEAD")
    ]

    q = query.strip().lower()
    if q:
        local_branches = [b for b in local_branches if q in b.lower()]
        remote_branches = [b for b in remote_branches if q in b.lower()]

    recent = [current_branch]
    for candidate in (default_branch, "develop", "release", "hotfix"):
        if candidate and candidate not in recent and (candidate in local_branches or candidate in remote_branches):
            recent.append(candidate)

    return {
        "current_branch": current_branch,
        "default_branch": default_branch,
        "recent_branches": recent[:8],
        "local_branches": sorted(set(local_branches)),
        "remote_branches": sorted(set(remote_branches)),
    }


def pull_latest(repo: Dict[str, Any], branch: Optional[str] = None) -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    target_branch = _normalize_branch_name(
        branch or _safe_run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], "")
    )
    if not target_branch:
        raise RuntimeError("Unable to resolve branch for pull operation.")

    _run_git(repo_root, ["fetch", "--all", "--prune"])
    _run_git(repo_root, ["pull", "--ff-only", "origin", target_branch])
    commit_sha = _safe_run_git(repo_root, ["rev-parse", "HEAD"], "unknown")

    return {
        "branch": target_branch,
        "commit_sha": commit_sha,
        "message": f"Pulled latest changes for '{target_branch}'.",
    }


def checkout_branch(repo: Dict[str, Any], branch: str, pull_after_checkout: bool = True) -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    target = _normalize_branch_name(branch)
    if not target:
        raise RuntimeError("Branch name is required.")

    _run_git(repo_root, ["fetch", "--all", "--prune"])

    local = _safe_run_git(repo_root, ["show-ref", "--verify", f"refs/heads/{target}"], "")
    if local:
        _run_git(repo_root, ["checkout", target])
    else:
        remote = _safe_run_git(repo_root, ["show-ref", "--verify", f"refs/remotes/origin/{target}"], "")
        if remote:
            _run_git(repo_root, ["checkout", "-B", target, f"origin/{target}"])
        else:
            raise RuntimeError(f"Branch '{target}' was not found locally or on origin.")

    pull_result = None
    if pull_after_checkout:
        try:
            pull_result = pull_latest(repo, target)
        except Exception as err:
            logger.warning(f"Pull latest failed after checkout for branch '{target}': {err}")

    state = get_branch_status(repo)
    return {
        "branch": target,
        "commit_sha": state.get("commit_sha", "unknown"),
        "pull_result": pull_result,
        "status": state,
        "message": f"Checked out branch '{target}'.",
    }


def return_to_default_branch(repo: Dict[str, Any], pull_after_checkout: bool = True) -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    default_branch = _detect_default_branch(repo_root)
    result = checkout_branch(repo, default_branch, pull_after_checkout=pull_after_checkout)
    result["default_branch"] = default_branch
    result["message"] = f"Returned to default branch '{default_branch}'."
    return result


def _ahead_behind(repo_root: str, branch: str) -> Tuple[int, int]:
    raw = _safe_run_git(repo_root, ["rev-list", "--left-right", "--count", f"origin/{branch}...{branch}"], "0\t0")
    parts = raw.replace(" ", "\t").split("\t")
    if len(parts) >= 2:
        try:
            behind = int(parts[0])
            ahead = int(parts[1])
            return ahead, behind
        except ValueError:
            pass
    return 0, 0


def get_branch_status(repo: Dict[str, Any]) -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    branch = _safe_run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], "unknown")
    commit_sha = _safe_run_git(repo_root, ["rev-parse", "HEAD"], "unknown")
    short_sha = commit_sha[:12] if commit_sha and commit_sha != "unknown" else "unknown"
    last_commit = _safe_run_git(repo_root, ["log", "-1", "--pretty=%s"], "")
    author = _safe_run_git(repo_root, ["log", "-1", "--pretty=%an"], "")
    commit_date = _safe_run_git(repo_root, ["log", "-1", "--pretty=%cI"], "")
    changed = _safe_run_git(repo_root, ["status", "--porcelain"], "")
    changed_files = [line for line in changed.splitlines() if line.strip()]
    ahead, behind = _ahead_behind(repo_root, branch)

    return {
        "current_branch": branch,
        "last_commit": last_commit,
        "author": author,
        "commit_sha": commit_sha,
        "short_commit_sha": short_sha,
        "ahead": ahead,
        "behind": behind,
        "changed_files": len(changed_files),
        "changed_paths": [line[3:] for line in changed_files[:50] if len(line) > 3],
        "default_branch": _detect_default_branch(repo_root),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "indexed_at": repo.get("indexed_at"),
        "index_status": "ready" if repo.get("status") == "ready" else repo.get("status") or "unknown",
    }


def compare_branches(repo: Dict[str, Any], base_branch: str, target_branch: str) -> Dict[str, Any]:
    repo_root = _repo_root(repo)
    base = _normalize_branch_name(base_branch)
    target = _normalize_branch_name(target_branch)
    if not base or not target:
        raise RuntimeError("Both base_branch and target_branch are required.")

    _run_git(repo_root, ["fetch", "--all", "--prune"])

    base_ref = _resolve_compare_ref(repo_root, base)
    target_ref = _resolve_compare_ref(repo_root, target)

    # Compare branch snapshots directly so file-count stays accurate regardless selector order.
    name_only = _run_git(repo_root, ["diff", "--name-only", "--no-renames", base_ref, target_ref])
    files = [line.strip() for line in name_only.splitlines() if line.strip()]

    categories = {
        "architecture": 0,
        "security": 0,
        "performance": 0,
        "technical_debt": 0,
        "api": 0,
        "database": 0,
        "business_logic": 0,
        "dependencies": 0,
    }

    for path in files:
        lower = path.lower()
        if any(token in lower for token in ("arch", "design", "module", "service", "router")):
            categories["architecture"] += 1
        if any(token in lower for token in ("auth", "security", "secret", "token", "permission")):
            categories["security"] += 1
        if any(token in lower for token in ("perf", "cache", "latency", "async", "optimi")):
            categories["performance"] += 1
        if any(token in lower for token in ("refactor", "legacy", "todo", "fixme")):
            categories["technical_debt"] += 1
        if any(token in lower for token in ("api/", "router", "endpoint", "controller")):
            categories["api"] += 1
        if any(token in lower for token in ("sql", "migration", "schema", "db", "database")):
            categories["database"] += 1
        if any(token in lower for token in ("service", "domain", "business", "workflow", "rule")):
            categories["business_logic"] += 1
        if any(token in lower for token in ("requirements", "package", "poetry", "npm", "pip", "cargo", "go.mod")):
            categories["dependencies"] += 1

    risk_points = categories["security"] * 3 + categories["database"] * 3 + categories["architecture"] * 2 + categories["technical_debt"]
    overall_score = max(0, 100 - risk_points)
    blocking_issues: List[str] = []
    warnings: List[str] = []

    if categories["security"] > 0:
        blocking_issues.append("Security-sensitive files changed; require security review.")
    if categories["database"] > 0:
        blocking_issues.append("Database or migration changes detected; require migration validation.")
    if categories["performance"] > 0:
        warnings.append("Performance-related changes detected; run targeted performance checks.")
    if categories["technical_debt"] > 0:
        warnings.append("Technical debt indicators changed; verify maintainability impact.")

    safe_to_merge = len(blocking_issues) == 0 and overall_score >= 75

    return {
        "base_branch": base,
        "target_branch": target,
        "changed_files": len(files),
        "sample_changed_files": files[:50],
        "architecture_changes": categories["architecture"],
        "security_changes": categories["security"],
        "performance_changes": categories["performance"],
        "technical_debt_changes": categories["technical_debt"],
        "api_changes": categories["api"],
        "database_changes": categories["database"],
        "business_logic_changes": categories["business_logic"],
        "dependency_changes": categories["dependencies"],
        "risk_assessment": "High" if risk_points >= 15 else "Medium" if risk_points >= 7 else "Low",
        "merge_readiness": {
            "overall_score": overall_score,
            "blocking_issues": blocking_issues,
            "warnings": warnings,
            "suggested_reviewers": ["Backend Lead", "Security Engineer"] if categories["security"] else ["Backend Lead"],
            "estimated_review_time_minutes": min(240, max(20, len(files) * 4)),
            "deployment_risk": "High" if categories["database"] > 0 or categories["security"] > 0 else "Medium" if len(files) > 30 else "Low",
            "safe_to_merge": safe_to_merge,
        },
        "ai_executive_summary": (
            f"Comparison {base} -> {target}: {len(files)} files changed. "
            f"Risk is {('high' if risk_points >= 15 else 'medium' if risk_points >= 7 else 'low')}. "
            f"Merge readiness score is {overall_score}/100 with {len(blocking_issues)} blocking issue(s)."
        ),
    }
