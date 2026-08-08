"""Repository Explorer services: secure file tree, file insights, reviews, fixes, and targeted tests."""

from __future__ import annotations

import ast
import difflib
import hashlib
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api.services.review_service import review_files
from app.config import get_repos_dir
from app.services.llm_fallback import generate_with_fallback
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MAX_TREE_ITEMS = 500
_MAX_FILE_CHARS = 200_000
_MAX_DIFF_CHARS = 400_000
_DEFAULT_TEST_TIMEOUT_SECONDS = 55

_FILE_HISTORY: Dict[Tuple[str, str], Dict[str, List[Dict[str, Any]]]] = {}
_FIX_PROPOSALS: Dict[str, Dict[str, Any]] = {}


_LANGUAGE_BY_EXT = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".json": "json",
    ".md": "markdown",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".sql": "sql",
    ".sh": "shell",
    ".ps1": "powershell",
    ".css": "css",
    ".scss": "scss",
    ".html": "html",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root_for(repo: Dict[str, Any]) -> str:
    repos_dir = get_repos_dir()
    index_name = str(repo.get("index_name") or "").strip()
    repo_name = str(repo.get("name") or "").strip()

    if index_name:
        preferred = os.path.join(repos_dir, index_name)
        if os.path.isdir(preferred):
            return preferred

    fallback = os.path.join(repos_dir, repo_name)
    if os.path.isdir(fallback):
        return fallback

    # Keep a deterministic root even when indexing output is missing.
    return os.path.join(repos_dir, index_name or repo_name)


def _safe_join(repo_root: str, relative_path: str) -> str:
    root_path = Path(repo_root).resolve()
    target = (root_path / relative_path).resolve()
    try:
        target.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("Path escapes repository root") from exc
    return str(target)


def _normalize_rel_path(path: str) -> str:
    raw = (path or "").strip().replace("\\", "/")
    if raw in {".", "./"}:
        return ""
    return raw.strip("/")


def _language_for(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return _LANGUAGE_BY_EXT.get(ext, "text")


def _health_indicator(name: str, language: str, size: int) -> str:
    lowered = name.lower()
    if "password" in lowered or "secret" in lowered:
        return "critical"
    if language in {"python", "typescript", "javascript"} and size > 60_000:
        return "review_suggested"
    if lowered.startswith("test_") or "/tests/" in lowered.replace("\\", "/"):
        return "healthy"
    return "not_analyzed"


def _ai_indicator(modified_at: float) -> str:
    if modified_at <= 0:
        return "not_analyzed"
    if (time.time() - modified_at) < (48 * 60 * 60):
        return "recently_changed"
    return "not_analyzed"


def _build_git_status_map(repo_root: str, scope_rel_path: str) -> Dict[str, str]:
    try:
        target = scope_rel_path or "."
        proc = subprocess.run(
            ["git", "-C", repo_root, "status", "--porcelain", "--", target],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return {}

    if proc.returncode != 0:
        return {}

    status_map: Dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        status = line[:2].strip() or "??"
        path = line[3:].strip().replace("\\", "/")
        if path.startswith("../"):
            continue
        status_map[path] = status
    return status_map


def list_directory_tree(
    repo: Dict[str, Any],
    *,
    relative_path: str = "",
    include_hidden: bool = False,
    limit: int = 200,
) -> Dict[str, Any]:
    logger.info(
        "Explorer list_directory_tree started: repo_id=%s path='%s' hidden=%s limit=%s",
        repo.get("id"),
        relative_path,
        include_hidden,
        limit,
    )
    repo_root = _repo_root_for(repo)
    rel = _normalize_rel_path(relative_path)

    if not os.path.isdir(repo_root):
        logger.warning("Explorer repo root missing: %s", repo_root)
        return {
            "repo_root": repo_root,
            "path": rel,
            "nodes": [],
            "truncated": False,
            "count": 0,
        }

    target_dir = _safe_join(repo_root, rel) if rel else repo_root
    if not os.path.isdir(target_dir):
        logger.warning("Explorer target directory missing: %s", target_dir)
        raise FileNotFoundError("Directory not found")

    effective_limit = max(1, min(limit, _MAX_TREE_ITEMS))
    git_status_map = _build_git_status_map(repo_root, rel)

    entries: List[os.DirEntry[str]] = []
    with os.scandir(target_dir) as scan:
        for entry in scan:
            name = entry.name
            if not include_hidden and name.startswith("."):
                continue
            entries.append(entry)

    entries.sort(
        key=lambda item: (
            not item.is_dir(follow_symlinks=False),
            item.name.lower(),
        )
    )

    nodes: List[Dict[str, Any]] = []
    for entry in entries[:effective_limit]:
        is_dir = entry.is_dir(follow_symlinks=False)
        full_path = entry.path
        rel_path = os.path.relpath(full_path, repo_root).replace("\\", "/")

        try:
            stat = entry.stat(follow_symlinks=False)
            modified_at = stat.st_mtime
            size = int(stat.st_size)
        except Exception:
            modified_at = 0.0
            size = 0

        language = "folder" if is_dir else _language_for(entry.name)
        git_status = git_status_map.get(rel_path, "")

        nodes.append(
            {
                "name": entry.name,
                "path": rel_path,
                "type": "folder" if is_dir else "file",
                "has_children": bool(is_dir and _folder_has_children(full_path, include_hidden=include_hidden)),
                "size": size,
                "modified_at": (
                    datetime.fromtimestamp(modified_at, tz=timezone.utc).isoformat()
                    if modified_at
                    else None
                ),
                "language": language,
                "health": _health_indicator(rel_path, language, size),
                "ai_indicator": _ai_indicator(modified_at),
                "git_status": git_status,
                "is_modified": bool(git_status),
            }
        )

    result = {
        "repo_root": repo_root,
        "path": rel,
        "nodes": nodes,
        "truncated": len(entries) > effective_limit,
        "count": len(nodes),
    }
    logger.info(
        "Explorer list_directory_tree completed: repo_id=%s nodes=%s truncated=%s",
        repo.get("id"),
        result["count"],
        result["truncated"],
    )
    return result


def _folder_has_children(folder_path: str, *, include_hidden: bool) -> bool:
    try:
        with os.scandir(folder_path) as scan:
            for entry in scan:
                if include_hidden or not entry.name.startswith("."):
                    return True
    except Exception:
        return False
    return False


def _safe_read_text(path: str, max_chars: int = _MAX_FILE_CHARS) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(max_chars)


def _git_last_modifier(repo_root: str, rel_path: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "log", "-1", "--format=%an|%aI", "--", rel_path],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if proc.returncode != 0:
            return None, None

        raw = (proc.stdout or "").strip()
        if not raw:
            return None, None
        owner, _, modified_at = raw.partition("|")
        owner = owner.strip() or None
        modified_at = modified_at.strip() or None
        return owner, modified_at
    except Exception:
        return None, None


def _python_structure(content: str) -> Dict[str, Any]:
    classes: List[str] = []
    functions: List[str] = []
    imports: List[str] = []
    complexity = 1

    try:
        tree = ast.parse(content)
    except Exception:
        return {
            "classes": classes,
            "functions": functions,
            "imports": imports,
            "complexity": complexity,
        }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names = ", ".join(alias.name for alias in node.names)
            imports.append(f"{base}:{names}" if base else names)
        elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.Match, ast.BoolOp, ast.IfExp, ast.comprehension)):
            complexity += 1

    return {
        "classes": sorted(set(classes)),
        "functions": sorted(set(functions)),
        "imports": sorted(set(imports)),
        "complexity": complexity,
    }


def get_file_details(repo: Dict[str, Any], *, relative_path: str) -> Dict[str, Any]:
    logger.info(
        "Explorer get_file_details started: repo_id=%s path='%s'",
        repo.get("id"),
        relative_path,
    )
    repo_root = _repo_root_for(repo)
    rel = _normalize_rel_path(relative_path)
    if not rel:
        raise ValueError("A file path is required")

    abs_path = _safe_join(repo_root, rel)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError("File not found")

    content = _safe_read_text(abs_path)
    try:
        stat = os.stat(abs_path)
        fs_modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    except Exception:
        fs_modified_at = None

    owner, git_modified_at = _git_last_modifier(repo_root, rel)
    lines = content.splitlines()
    language = _language_for(rel)

    structure = _python_structure(content) if language == "python" else {
        "classes": [],
        "functions": [],
        "imports": _heuristic_imports(content),
        "complexity": _heuristic_complexity(content),
    }

    summary = _build_file_summary(rel, language, lines, structure)
    digest = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()

    result = {
        "path": rel,
        "language": language,
        "content": content,
        "sha256": digest,
        "summary": summary,
        "complexity": structure["complexity"],
        "health": _health_indicator(rel, language, len(content)),
        "dependencies": {
            "imports": structure["imports"],
            "imported_by": [],
            "calls": [],
            "called_by": [],
        },
        "classes": structure["classes"],
        "functions": structure["functions"],
        "imports": structure["imports"],
        "line_count": len(lines),
        "size": len(content),
        "owner": owner,
        "last_modified": git_modified_at or fs_modified_at,
    }
    logger.info(
        "Explorer get_file_details completed: path='%s' language=%s lines=%s",
        rel,
        language,
        len(lines),
    )
    return result


def _heuristic_imports(content: str) -> List[str]:
    imports: List[str] = []
    for line in content.splitlines()[:400]:
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            imports.append(stripped)
        elif stripped.startswith("require(") or " from '" in stripped or ' from "' in stripped:
            imports.append(stripped)
    return imports[:200]


def _heuristic_complexity(content: str) -> int:
    text = content.lower()
    complexity_tokens = (" if ", " for ", " while ", " try:", " catch", "&&", "||", "switch", "case ")
    return 1 + sum(text.count(token) for token in complexity_tokens)


def _build_file_summary(path: str, language: str, lines: List[str], structure: Dict[str, Any]) -> str:
    total = len(lines)
    non_empty = sum(1 for line in lines if line.strip())
    return (
        f"{path} is a {language} source file with {total} lines ({non_empty} non-empty). "
        f"Detected {len(structure.get('classes', []))} classes, "
        f"{len(structure.get('functions', []))} functions, and "
        f"{len(structure.get('imports', []))} imports."
    )


def review_single_file(repo: Dict[str, Any], *, relative_path: str, prompt: str = "") -> Dict[str, Any]:
    logger.info(
        "Explorer review_single_file started: repo_id=%s path='%s'",
        repo.get("id"),
        relative_path,
    )
    review = _run_review(repo, [relative_path], prompt=prompt)
    result = {
        "review_id": f"explorer-{int(time.time() * 1000)}",
        "scope": "file",
        "overall_score": _score_from_findings(review.get("findings") or []),
        "summary": review.get("summary") or "Review completed",
        "findings": review.get("findings") or [],
        "changed_files": review.get("changed_files") or [],
        "sections": _review_sections(review.get("findings") or []),
        "generated_at": _now_iso(),
    }
    _record_history(str(repo.get("id") or ""), relative_path, "reviews", result)
    logger.info(
        "Explorer review_single_file completed: path='%s' findings=%s score=%s",
        relative_path,
        len(result.get("findings") or []),
        result.get("overall_score"),
    )
    return result


def review_multiple_files(repo: Dict[str, Any], *, relative_paths: List[str], prompt: str = "") -> Dict[str, Any]:
    logger.info(
        "Explorer review_multiple_files started: repo_id=%s file_count=%s",
        repo.get("id"),
        len(relative_paths),
    )
    review = _run_review(repo, relative_paths, prompt=prompt)
    result = {
        "review_id": f"explorer-batch-{int(time.time() * 1000)}",
        "scope": "files",
        "overall_score": _score_from_findings(review.get("findings") or []),
        "summary": review.get("summary") or "Review completed",
        "findings": review.get("findings") or [],
        "changed_files": review.get("changed_files") or [],
        "sections": _review_sections(review.get("findings") or []),
        "generated_at": _now_iso(),
    }
    for rel in relative_paths:
        _record_history(str(repo.get("id") or ""), rel, "reviews", result)
    logger.info(
        "Explorer review_multiple_files completed: findings=%s score=%s",
        len(result.get("findings") or []),
        result.get("overall_score"),
    )
    return result


def _run_review(repo: Dict[str, Any], relative_paths: List[str], prompt: str) -> Dict[str, Any]:
    # review_files is async; this helper isolates the runner for sync router context.
    import asyncio

    async def _inner() -> Dict[str, Any]:
        return await review_files(repo=repo, file_paths=relative_paths, prompt=prompt)

    logger.info("Explorer _run_review invoking async review_files for %s path(s)", len(relative_paths))
    return asyncio.run(_inner())


def _score_from_findings(findings: List[Dict[str, Any]]) -> int:
    penalties = {"critical": 30, "high": 15, "medium": 7, "low": 3}
    score = 100
    for item in findings:
        sev = str(item.get("severity") or "medium").lower()
        score -= penalties.get(sev, 5)
    return max(0, score)


def _review_sections(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    critical = [f for f in findings if str(f.get("severity", "")).lower() == "critical"]
    warnings = [f for f in findings if str(f.get("severity", "")).lower() in {"high", "medium"}]
    suggestions = [f for f in findings if str(f.get("severity", "")).lower() == "low"]
    security = [f for f in findings if "security" in str(f.get("code_area", "")).lower()]
    performance = [f for f in findings if "performance" in str(f.get("code_area", "")).lower()]

    return {
        "critical_issues": critical,
        "warnings": warnings,
        "suggestions": suggestions,
        "code_smells": suggestions,
        "security_risks": security,
        "performance_risks": performance,
        "maintainability": {"score": max(0, 100 - len(warnings) * 8 - len(suggestions) * 4)},
        "testing_gaps": [f for f in findings if "test" in str(f.get("recommendation", "")).lower()],
    }


def generate_fix_proposal(
    repo: Dict[str, Any],
    *,
    relative_path: str,
    finding: str,
    recommendation: str = "",
) -> Dict[str, Any]:
    logger.info(
        "Explorer generate_fix_proposal started: repo_id=%s path='%s'",
        repo.get("id"),
        relative_path,
    )
    details = get_file_details(repo, relative_path=relative_path)
    current = details["content"]

    prompt = (
        "You are a principal engineer creating a safe, minimal code fix. Return the full updated file content only, "
        "without markdown fences. Preserve behavior outside the targeted fix.\n\n"
        f"TARGET_FILE: {relative_path}\n"
        f"FINDING: {finding}\n"
        f"RECOMMENDATION: {recommendation}\n\n"
        "CURRENT_FILE_CONTENT:\n"
        f"{current[:_MAX_DIFF_CHARS]}"
    )

    try:
        generated = _strip_code_fences(asyncio_run(generate_with_fallback(prompt))).strip()
    except Exception as err:
        logger.warning(f"Fix generation failed, fallback no-op applied: {err}")
        generated = current

    if not generated:
        generated = current

    diff_text = "\n".join(
        difflib.unified_diff(
            current.splitlines(),
            generated.splitlines(),
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
        )
    )

    fix_id = hashlib.sha1(f"{relative_path}:{time.time_ns()}".encode("utf-8")).hexdigest()[:16]
    payload = {
        "fix_id": fix_id,
        "path": relative_path,
        "current_content": current,
        "suggested_content": generated,
        "diff": diff_text,
        "current_sha256": details["sha256"],
        "generated_at": _now_iso(),
    }
    _FIX_PROPOSALS[fix_id] = payload
    _record_history(str(repo.get("id") or ""), relative_path, "fixes", payload)
    logger.info("Explorer generate_fix_proposal completed: fix_id=%s", fix_id)
    return payload


def apply_fix_proposal(
    repo: Dict[str, Any],
    *,
    fix_id: str,
    expected_sha256: Optional[str] = None,
    run_validation: bool = True,
) -> Dict[str, Any]:
    logger.info(
        "Explorer apply_fix_proposal started: repo_id=%s fix_id=%s validate=%s",
        repo.get("id"),
        fix_id,
        run_validation,
    )
    proposal = _FIX_PROPOSALS.get(fix_id)
    if not proposal:
        raise FileNotFoundError("Fix proposal not found")

    path = str(proposal["path"])
    repo_root = _repo_root_for(repo)
    abs_path = _safe_join(repo_root, _normalize_rel_path(path))
    if not os.path.isfile(abs_path):
        raise FileNotFoundError("Target file not found")

    current = _safe_read_text(abs_path)
    live_sha = hashlib.sha256(current.encode("utf-8", errors="ignore")).hexdigest()
    if expected_sha256 and live_sha != expected_sha256:
        raise ValueError("File has changed since fix generation")

    original = current
    suggested = str(proposal["suggested_content"])

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(suggested)

    validation = {
        "formatter": "skipped",
        "linter": "skipped",
        "static_analysis": "skipped",
        "tests": "skipped",
    }
    try:
        if run_validation:
            validation = _validate_change(repo_root, path)
            if any(value.startswith("failed") for value in validation.values()):
                raise RuntimeError("Validation failed")
    except Exception as err:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(original)
        _record_history(
            str(repo.get("id") or ""),
            path,
            "rejected_fixes",
            {"fix_id": fix_id, "reason": str(err), "at": _now_iso()},
        )
        raise ValueError(f"Fix rejected: {err}") from err

    applied = {
        "fix_id": fix_id,
        "path": path,
        "applied": True,
        "validation": validation,
        "applied_at": _now_iso(),
    }
    _record_history(str(repo.get("id") or ""), path, "applied_fixes", applied)
    logger.info("Explorer apply_fix_proposal completed: fix_id=%s path='%s'", fix_id, path)
    return applied


def _validate_change(repo_root: str, relative_path: str) -> Dict[str, str]:
    logger.info("Explorer _validate_change started: path='%s'", relative_path)
    target_abs = _safe_join(repo_root, relative_path)
    results = {
        "formatter": "skipped",
        "linter": "skipped",
        "static_analysis": "ok",
        "tests": "ok",
    }

    # Static analysis: Python files must parse.
    if relative_path.endswith(".py"):
        try:
            ast.parse(_safe_read_text(target_abs))
            results["static_analysis"] = "ok"
        except Exception as err:
            results["static_analysis"] = f"failed: {err}"
            return results

    # Optional formatter/linter checks only when tools are installed.
    fmt = _run_optional_command(["python", "-m", "black", "--check", target_abs], cwd=repo_root)
    if fmt is not None:
        results["formatter"] = "ok" if fmt["ok"] else f"failed: {fmt['stderr'] or fmt['stdout'] or 'black --check'}"
        if not fmt["ok"]:
            return results

    lint = _run_optional_command(["python", "-m", "ruff", "check", target_abs], cwd=repo_root)
    if lint is not None:
        results["linter"] = "ok" if lint["ok"] else f"failed: {lint['stderr'] or lint['stdout'] or 'ruff check'}"
        if not lint["ok"]:
            return results

    tests = discover_impacted_tests(
        {
            "index_name": os.path.basename(repo_root),
            "name": os.path.basename(repo_root),
            "id": "local",
        },
        relative_paths=[relative_path],
        force_repo_root=repo_root,
    )
    selected = tests.get("tests", [])[:8]
    if selected:
        outcome = run_targeted_tests(
            {
                "index_name": os.path.basename(repo_root),
                "name": os.path.basename(repo_root),
                "id": "local",
            },
            tests=selected,
            timeout_seconds=_DEFAULT_TEST_TIMEOUT_SECONDS,
            force_repo_root=repo_root,
        )
        if outcome.get("status") != "passed":
            results["tests"] = f"failed: {outcome.get('status')}"
            return results

    logger.info("Explorer _validate_change completed: path='%s'", relative_path)
    return results


def _run_optional_command(cmd: List[str], *, cwd: str) -> Optional[Dict[str, Any]]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=20, check=False)
    except Exception:
        return None
    return {
        "ok": proc.returncode == 0,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def discover_impacted_tests(
    repo: Dict[str, Any],
    *,
    relative_paths: List[str],
    force_repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info(
        "Explorer discover_impacted_tests started: repo_id=%s paths=%s",
        repo.get("id"),
        len(relative_paths),
    )
    repo_root = force_repo_root or _repo_root_for(repo)
    tests_root = os.path.join(repo_root, "tests")
    discovered: List[str] = []

    if not os.path.isdir(tests_root):
        return {"tests": [], "count": 0}

    candidates = _collect_test_candidates(relative_paths)
    for test_path in _iter_repo_files(tests_root):
        rel = os.path.relpath(test_path, repo_root).replace("\\", "/")
        low_rel = rel.lower()
        if any(token in low_rel for token in candidates):
            discovered.append(rel)

    deduped = sorted(set(discovered))
    result = {"tests": deduped[:80], "count": len(deduped)}
    logger.info(
        "Explorer discover_impacted_tests completed: repo_id=%s discovered=%s",
        repo.get("id"),
        result["count"],
    )
    return result


def _collect_test_candidates(relative_paths: List[str]) -> List[str]:
    tokens: List[str] = []
    for path in relative_paths:
        rel = _normalize_rel_path(path)
        base = os.path.splitext(os.path.basename(rel))[0].lower()
        if base:
            tokens.append(base)
            tokens.append(f"test_{base}")
        parts = [p.lower() for p in rel.split("/") if p]
        if parts:
            tokens.extend(parts[-2:])
    return sorted(set(t for t in tokens if t))


def _iter_repo_files(root: str):
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {"__pycache__", "node_modules", ".next", "dist", "build"}]
        for filename in files:
            if filename.startswith("."):
                continue
            yield os.path.join(current_root, filename)


def run_targeted_tests(
    repo: Dict[str, Any],
    *,
    tests: List[str],
    timeout_seconds: int = _DEFAULT_TEST_TIMEOUT_SECONDS,
    force_repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info(
        "Explorer run_targeted_tests started: repo_id=%s tests=%s timeout=%s",
        repo.get("id"),
        len(tests),
        timeout_seconds,
    )
    repo_root = force_repo_root or _repo_root_for(repo)
    if not tests:
        return {
            "status": "skipped",
            "tests": [],
            "passed": 0,
            "failed": 0,
            "duration_seconds": 0.0,
            "coverage": None,
            "output": "No impacted tests discovered.",
        }

    cmd = ["python", "-m", "pytest", "-q", "--maxfail=1", *tests]
    logger.info("Explorer run_targeted_tests command: %s", " ".join(cmd))
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=max(5, timeout_seconds),
            check=False,
        )
        duration = round(time.time() - started, 3)
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "tests": tests,
            "passed": 0,
            "failed": len(tests),
            "duration_seconds": float(timeout_seconds),
            "coverage": None,
            "output": f"Timed out after {timeout_seconds} seconds",
        }

    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    passed, failed = _parse_pytest_counts(combined)
    status = "passed" if proc.returncode == 0 else "failed"

    result = {
        "status": status,
        "tests": tests,
        "passed": passed,
        "failed": failed,
        "duration_seconds": duration,
        "coverage": None,
        "output": combined[-12_000:],
    }
    for test_item in tests:
        _record_history(str(repo.get("id") or ""), test_item, "test_runs", result)
    logger.info(
        "Explorer run_targeted_tests completed: status=%s passed=%s failed=%s duration=%s",
        status,
        passed,
        failed,
        duration,
    )
    return result


def _parse_pytest_counts(output: str) -> Tuple[int, int]:
    passed = 0
    failed = 0
    text = output.lower()

    import re

    m = re.search(r"(\d+)\s+passed", text)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", text)
    if m:
        failed = int(m.group(1))
    return passed, failed


def append_conversation_entry(repo_id: str, path: str, role: str, content: str) -> Dict[str, Any]:
    logger.info("Explorer append_conversation_entry: repo_id=%s path='%s' role=%s", repo_id, path, role)
    entry = {
        "role": role,
        "content": content,
        "created_at": _now_iso(),
    }
    _record_history(repo_id, path, "conversations", entry)
    return entry


def get_file_history(repo_id: str, path: str) -> Dict[str, Any]:
    logger.info("Explorer get_file_history: repo_id=%s path='%s'", repo_id, path)
    key = (repo_id, _normalize_rel_path(path))
    data = _FILE_HISTORY.get(key, {})
    return {
        "path": key[1],
        "reviews": data.get("reviews", []),
        "fixes": data.get("fixes", []),
        "applied_fixes": data.get("applied_fixes", []),
        "rejected_fixes": data.get("rejected_fixes", []),
        "test_runs": data.get("test_runs", []),
        "conversations": data.get("conversations", []),
    }


def _record_history(repo_id: str, path: str, bucket: str, payload: Dict[str, Any]) -> None:
    key = (repo_id, _normalize_rel_path(path))
    per_file = _FILE_HISTORY.setdefault(key, {})
    values = per_file.setdefault(bucket, [])
    values.insert(0, payload)
    if len(values) > 30:
        del values[30:]
    logger.debug(
        "Explorer history updated: repo_id=%s path='%s' bucket=%s size=%s",
        repo_id,
        key[1],
        bucket,
        len(values),
    )


def _strip_code_fences(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 2:
            raw = "\n".join(lines[1:-1]).strip()
    return raw


def asyncio_run(awaitable):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # FastAPI endpoint is already async; run in thread-safe way via nested loop.
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(awaitable)
        finally:
            new_loop.close()

    return asyncio.run(awaitable)

