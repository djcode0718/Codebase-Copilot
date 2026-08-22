import os
import stat
import shutil
import subprocess
import git
import threading
import uuid
from urllib.parse import urlparse, quote
from typing import Optional
from app.config import REPOS_DIR
from app.ingestion.repo_naming import derive_repo_name, is_valid_url, normalize_clone_source
from app.utils.git_auth import get_git_auth_token
from app.utils.logger import get_logger
import time

logger = get_logger(__name__)

_REPO_DIR_LOCKS = {}
_REPO_DIR_LOCKS_GUARD = threading.Lock()


class CloneRepositoryError(RuntimeError):
    """Raised when clone fails with enough context for SSE diagnostics."""

    def __init__(self, message: str, clone_source: str, clone_target_path: str):
        super().__init__(message)
        self.clone_source = clone_source
        self.clone_target_path = clone_target_path


def _is_errno_22(error: Exception) -> bool:
    current = error
    while current is not None:
        if isinstance(current, OSError) and getattr(current, "errno", None) == 22:
            return True
        current = getattr(current, "__cause__", None)
    lowered = str(error).lower()
    return (
        "[errno 22]" in lowered
        or "winerror 87" in lowered
        or "invalid argument" in lowered
    )


def _build_windows_short_target_dir(repo_name: str, primary_target_dir: str) -> str | None:
    if os.name != "nt":
        return None

    primary_abs = os.path.abspath(primary_target_dir)
    primary_drive = os.path.splitdrive(primary_abs)[0] or "C:"
    short_root = os.path.join(f"{primary_drive}\\", "cb-repos")
    short_target = os.path.abspath(os.path.join(short_root, repo_name))

    if os.path.normcase(short_target) == os.path.normcase(primary_abs):
        return None

    os.makedirs(short_root, exist_ok=True)
    return short_target


def _get_repo_dir_lock(path: str) -> threading.Lock:
    key = os.path.normcase(os.path.abspath(path))
    with _REPO_DIR_LOCKS_GUARD:
        lock = _REPO_DIR_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _REPO_DIR_LOCKS[key] = lock
        return lock


def _on_rmtree_error(func, path, exc_info):
    # Windows can mark git pack files read-only; flip the bit and retry once.
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    func(path)


def _rmtree_with_retry(path: str, attempts: int = 8, base_delay_s: float = 0.12) -> None:
    if not os.path.exists(path):
        return

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            shutil.rmtree(path, onerror=_on_rmtree_error)
            return
        except FileNotFoundError:
            return
        except (PermissionError, OSError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            delay = min(base_delay_s * (2 ** (attempt - 1)), 1.2)
            logger.warning(
                "Retrying repository cleanup for %s (attempt %s/%s): %s",
                path,
                attempt,
                attempts,
                exc,
            )
            time.sleep(delay)

    raise last_error


def _move_aside_and_cleanup(path: str) -> None:
    moved_path = f"{path}.deleting-{uuid.uuid4().hex[:8]}"
    os.replace(path, moved_path)
    try:
        _rmtree_with_retry(moved_path, attempts=4, base_delay_s=0.1)
    except Exception as exc:
        # Best effort: keep startup/indexing moving even if background cleanup is delayed.
        logger.warning("Deferred cleanup failed for %s: %s", moved_path, exc)


def _remove_existing_repo_dir(target_dir: str) -> None:
    if not os.path.exists(target_dir):
        return

    logger.info(f"Removing existing directory {target_dir}")
    try:
        _rmtree_with_retry(target_dir)
    except Exception as exc:
        logger.warning("Direct cleanup failed for %s: %s. Trying move-aside strategy.", target_dir, exc)
        _move_aside_and_cleanup(target_dir)



def _build_authenticated_url(source: str, token: Optional[str] = None) -> str:
    """Inject a GitHub token into HTTPS URL when available for private repos."""
    token = (token or get_git_auth_token() or "").strip()
    if not token:
        return source

    parsed = urlparse(source)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return source
    if parsed.username:
        return source

    safe_token = quote(token, safe="")
    netloc = f"x-access-token:{safe_token}@{parsed.netloc}"
    return parsed._replace(netloc=netloc).geturl()


def _is_auth_error(message: str) -> bool:
    lowered = (message or "").lower()
    auth_signals = (
        "authentication failed",
        "could not read username",
        "access denied",
        "repository not found",
        "terminal prompts disabled",
        "support for password authentication was removed",
    )
    return any(signal in lowered for signal in auth_signals)


def _clone_repository(source: str, target_dir: str) -> None:
    """Clone with non-interactive git settings to fail fast on auth issues."""
    token = (get_git_auth_token() or "").strip()
    parsed = urlparse(source)
    is_github_https = parsed.scheme == "https" and parsed.hostname == "github.com"
    clone_env = os.environ.copy()
    clone_env["GIT_TERMINAL_PROMPT"] = "0"
    clone_env.pop("GIT_ASKPASS", None)
    clone_env["GCM_INTERACTIVE"] = "Never"

    def _clone_with_git_cli(clone_source: str) -> None:
        args = [
            "git",
            "-c",
            "core.longpaths=true",
            "-c",
            "core.protectNTFS=false",
            "clone",
            clone_source,
            target_dir,
        ]
        result = subprocess.run(
            args,
            env=clone_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        details = stderr or stdout or f"git exited with code {result.returncode}"
        if _is_auth_error(details):
            raise ValueError(
                "Git clone authentication failed. This repository may be private. "
                "Set GIT_AUTH_TOKEN (or GITHUB_TOKEN) in backend environment with repo read access."
            )
        raise RuntimeError(details)

    try:
        # Public repositories should clone without credentials first.
        git.Repo.clone_from(source, target_dir, env=clone_env)
    except OSError as os_err:
        # GitPython can throw Errno 22 on some Windows clone invocations; retry via git CLI.
        if _is_errno_22(os_err):
            _remove_existing_repo_dir(target_dir)
            _clone_with_git_cli(source)
            return
        raise
    except git.exc.GitCommandError as e:
        err = str(e)
        if not _is_auth_error(err):
            raise

        # Retry with token only for GitHub HTTPS repos where auth is likely needed.
        if is_github_https and token:
            _remove_existing_repo_dir(target_dir)
            try:
                authed_source = _build_authenticated_url(source, token=token)
                try:
                    git.Repo.clone_from(authed_source, target_dir, env=clone_env)
                except OSError as os_err:
                    if _is_errno_22(os_err):
                        _remove_existing_repo_dir(target_dir)
                        _clone_with_git_cli(authed_source)
                    else:
                        raise
                return
            except git.exc.GitCommandError as retry_err:
                if not _is_auth_error(str(retry_err)):
                    raise

        if _is_auth_error(err):
            raise ValueError(
                "Git clone authentication failed. This repository may be private. "
                "Set GIT_AUTH_TOKEN (or GITHUB_TOKEN) in backend environment with repo read access."
            ) from e
        raise

def load_repository(source: str) -> str:
    """
    Clones a GitHub repository or validates a local path.
    Returns the local path to the repository.
    """
    if is_valid_url(source):
        logger.info(f"Source identified as URL: {source}")
        clone_source = normalize_clone_source(source)
        repo_name = derive_repo_name(source)

        target_dir = os.path.join(REPOS_DIR, repo_name)
        candidate_targets = [target_dir]
        short_target_dir = _build_windows_short_target_dir(repo_name, target_dir)
        if short_target_dir:
            candidate_targets.append(short_target_dir)

        start_time = time.time()
        last_error = None

        for candidate_target in candidate_targets:
            repo_lock = _get_repo_dir_lock(candidate_target)
            with repo_lock:
                stage_dir = f"{candidate_target}.clone-{uuid.uuid4().hex[:8]}"
                logger.info("Cloning repository into staging path %s", stage_dir)
                _remove_existing_repo_dir(stage_dir)

                try:
                    _clone_repository(clone_source, stage_dir)
                    _remove_existing_repo_dir(candidate_target)
                    os.replace(stage_dir, candidate_target)
                    logger.info(
                        "Cloning completed in %.2fs (final path: %s)",
                        time.time() - start_time,
                        candidate_target,
                    )
                    return candidate_target
                except Exception as exc:
                    last_error = exc
                    _remove_existing_repo_dir(stage_dir)
                    can_retry_with_next_target = (
                        candidate_target != candidate_targets[-1]
                        and (_is_errno_22(exc) or isinstance(exc, (PermissionError, OSError)))
                    )
                    if can_retry_with_next_target:
                        logger.warning(
                            "Clone failed at %s (%s). Retrying with alternate target.",
                            candidate_target,
                            exc,
                        )
                        continue
                    break

        final_target = candidate_targets[-1] if short_target_dir else target_dir
        raise CloneRepositoryError(str(last_error), clone_source, final_target) from last_error
    else:
        logger.info(f"Source identified as local path: {source}")
        if not os.path.exists(source) or not os.path.isdir(source):
            raise ValueError(f"Invalid local directory path: {source}")
        return source
