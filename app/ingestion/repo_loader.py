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


def _redact_clone_source_for_log(source: str) -> str:
    """Return a source string that is safe to include in logs."""
    try:
        parsed = urlparse(source)
        if parsed.scheme and parsed.netloc:
            if parsed.username or parsed.password:
                host = parsed.hostname or ""
                if parsed.port:
                    host = f"{host}:{parsed.port}"
                return parsed._replace(netloc=host).geturl()
    except Exception:
        pass
    return source


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
        logger.debug("Skipping Windows short target path because platform is not Windows")
        return None

    primary_abs = os.path.abspath(primary_target_dir)
    primary_drive = os.path.splitdrive(primary_abs)[0] or "C:"
    short_root = os.path.join(f"{primary_drive}\\", "cb-repos")
    short_target = os.path.abspath(os.path.join(short_root, repo_name))

    if os.path.normcase(short_target) == os.path.normcase(primary_abs):
        logger.debug("Windows short target path matches primary path; no alternate target needed")
        return None

    os.makedirs(short_root, exist_ok=True)
    logger.debug("Prepared alternate Windows short target directory: %s", short_target)
    return short_target


def _get_repo_dir_lock(path: str) -> threading.Lock:
    key = os.path.normcase(os.path.abspath(path))
    with _REPO_DIR_LOCKS_GUARD:
        lock = _REPO_DIR_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _REPO_DIR_LOCKS[key] = lock
            logger.debug("Created new repository directory lock for %s", key)
        else:
            logger.debug("Reusing existing repository directory lock for %s", key)
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
        logger.debug("Cleanup skipped because path does not exist: %s", path)
        return

    logger.debug("Starting recursive cleanup for %s (attempts=%s, base_delay=%.2fs)", path, attempts, base_delay_s)

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            shutil.rmtree(path, onerror=_on_rmtree_error)
            logger.debug("Recursive cleanup succeeded for %s on attempt %s", path, attempt)
            return
        except FileNotFoundError:
            logger.debug("Cleanup target vanished during retry loop: %s", path)
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
    logger.debug("Moving %s aside to %s before cleanup retry", path, moved_path)
    os.replace(path, moved_path)
    try:
        _rmtree_with_retry(moved_path, attempts=4, base_delay_s=0.1)
    except Exception as exc:
        # Best effort: keep startup/indexing moving even if background cleanup is delayed.
        logger.warning("Deferred cleanup failed for %s: %s", moved_path, exc)


def _promote_staged_clone(stage_dir: str, target_dir: str, attempts: int = 8, base_delay_s: float = 0.12) -> None:
    """Promote a staged clone directory into the final target path with retries."""
    logger.debug(
        "Starting staged clone promotion (stage=%s, target=%s, attempts=%s, base_delay=%.2fs)",
        stage_dir,
        target_dir,
        attempts,
        base_delay_s,
    )

    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            os.replace(stage_dir, target_dir)
            logger.debug(
                "Staged clone promotion succeeded (stage=%s, target=%s, attempt=%s)",
                stage_dir,
                target_dir,
                attempt,
            )
            return
        except FileNotFoundError:
            logger.error(
                "Staged clone promotion failed because stage path is missing (stage=%s, target=%s)",
                stage_dir,
                target_dir,
            )
            raise
        except (PermissionError, OSError) as exc:
            last_error = exc
            stage_exists = os.path.exists(stage_dir)
            target_exists = os.path.exists(target_dir)
            logger.warning(
                "Staged clone promotion retry needed (attempt %s/%s, stage=%s, target=%s, "
                "stage_exists=%s, target_exists=%s, winerror=%s, error=%s)",
                attempt,
                attempts,
                stage_dir,
                target_dir,
                stage_exists,
                target_exists,
                getattr(exc, "winerror", None),
                exc,
            )

            if target_exists:
                try:
                    logger.debug("Promotion retry cleanup: removing target before next attempt (%s)", target_dir)
                    _remove_existing_repo_dir(target_dir)
                except Exception as cleanup_exc:
                    logger.warning(
                        "Promotion retry cleanup failed for %s: %s",
                        target_dir,
                        cleanup_exc,
                    )

            if attempt == attempts:
                break

            delay = min(base_delay_s * (2 ** (attempt - 1)), 1.2)
            time.sleep(delay)

    raise last_error


def _remove_existing_repo_dir(target_dir: str) -> None:
    if not os.path.exists(target_dir):
        logger.debug("Directory removal skipped because target does not exist: %s", target_dir)
        return

    logger.info(f"Removing existing directory {target_dir}")
    try:
        _rmtree_with_retry(target_dir)
        logger.debug("Directory removal completed for %s", target_dir)
    except Exception as exc:
        logger.warning("Direct cleanup failed for %s: %s. Trying move-aside strategy.", target_dir, exc)
        _move_aside_and_cleanup(target_dir)



def _build_authenticated_url(source: str, token: Optional[str] = None) -> str:
    """Inject a GitHub token into HTTPS URL when available for private repos."""
    token = (token or get_git_auth_token() or "").strip()
    if not token:
        logger.debug("No Git auth token detected; clone URL left unchanged")
        return source

    parsed = urlparse(source)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        logger.debug("Clone source is not GitHub HTTPS; token injection skipped")
        return source
    if parsed.username:
        logger.debug("Clone source already includes credentials; token injection skipped")
        return source

    safe_token = quote(token, safe="")
    netloc = f"x-access-token:{safe_token}@{parsed.netloc}"
    logger.debug("Injected GitHub token into clone URL for authenticated retry")
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
    safe_source = _redact_clone_source_for_log(source)
    clone_env = os.environ.copy()
    clone_env["GIT_TERMINAL_PROMPT"] = "0"
    clone_env.pop("GIT_ASKPASS", None)
    clone_env["GCM_INTERACTIVE"] = "Never"
    logger.debug(
        "Preparing clone operation (source=%s, target=%s, github_https=%s, token_present=%s)",
        safe_source,
        target_dir,
        is_github_https,
        bool(token),
    )

    def _clone_with_git_cli(clone_source: str) -> None:
        safe_cli_source = _redact_clone_source_for_log(clone_source)
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
        logger.debug("Running git CLI clone fallback (source=%s, target=%s)", safe_cli_source, target_dir)
        result = subprocess.run(
            args,
            env=clone_env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            logger.debug("git CLI clone fallback succeeded (source=%s)", safe_cli_source)
            return
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        details = stderr or stdout or f"git exited with code {result.returncode}"
        logger.warning(
            "git CLI clone fallback failed (source=%s, return_code=%s): %s",
            safe_cli_source,
            result.returncode,
            details,
        )
        if _is_auth_error(details):
            raise ValueError(
                "Git clone authentication failed. This repository may be private. "
                "Set GIT_AUTH_TOKEN (or GITHUB_TOKEN) in backend environment with repo read access."
            )
        raise RuntimeError(details)

    try:
        # Public repositories should clone without credentials first.
        logger.debug("Attempting primary GitPython clone (source=%s, target=%s)", safe_source, target_dir)
        git.Repo.clone_from(source, target_dir, env=clone_env)
        logger.debug("Primary GitPython clone succeeded (source=%s)", safe_source)
    except OSError as os_err:
        # GitPython can throw Errno 22 on some Windows clone invocations; retry via git CLI.
        logger.warning("Primary GitPython clone raised OSError for %s: %s", safe_source, os_err)
        if _is_errno_22(os_err):
            logger.info("Detected Errno 22 clone failure; retrying with git CLI for %s", safe_source)
            _remove_existing_repo_dir(target_dir)
            _clone_with_git_cli(source)
            return
        raise
    except git.exc.GitCommandError as e:
        err = str(e)
        logger.warning("Primary GitPython clone command failed for %s: %s", safe_source, err)
        if not _is_auth_error(err):
            raise

        # Retry with token only for GitHub HTTPS repos where auth is likely needed.
        if is_github_https and token:
            logger.info("Auth-related clone failure detected; retrying with GitHub token for %s", safe_source)
            _remove_existing_repo_dir(target_dir)
            try:
                authed_source = _build_authenticated_url(source, token=token)
                safe_authed_source = _redact_clone_source_for_log(authed_source)
                try:
                    logger.debug("Attempting authenticated GitPython clone (source=%s, target=%s)", safe_authed_source, target_dir)
                    git.Repo.clone_from(authed_source, target_dir, env=clone_env)
                    logger.debug("Authenticated GitPython clone succeeded (source=%s)", safe_authed_source)
                except OSError as os_err:
                    logger.warning("Authenticated GitPython clone raised OSError for %s: %s", safe_authed_source, os_err)
                    if _is_errno_22(os_err):
                        logger.info("Detected Errno 22 during authenticated clone; retrying with git CLI")
                        _remove_existing_repo_dir(target_dir)
                        _clone_with_git_cli(authed_source)
                    else:
                        raise
                return
            except git.exc.GitCommandError as retry_err:
                logger.warning("Authenticated GitPython clone failed for %s: %s", safe_source, retry_err)
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
    safe_source = _redact_clone_source_for_log(source)
    logger.info("Starting repository load workflow for source=%s", safe_source)
    if is_valid_url(source):
        logger.info("Source identified as remote URL")
        clone_source = normalize_clone_source(source)
        repo_name = derive_repo_name(source)
        logger.debug(
            "Normalized clone inputs (source=%s, normalized=%s, repo_name=%s)",
            safe_source,
            _redact_clone_source_for_log(clone_source),
            repo_name,
        )

        target_dir = os.path.join(REPOS_DIR, repo_name)
        candidate_targets = [target_dir]
        short_target_dir = _build_windows_short_target_dir(repo_name, target_dir)
        if short_target_dir:
            candidate_targets.append(short_target_dir)
        logger.info("Clone target candidates prepared: %s", candidate_targets)

        start_time = time.time()
        last_error = None

        for index, candidate_target in enumerate(candidate_targets, start=1):
            logger.info(
                "Clone target attempt %s/%s using path %s",
                index,
                len(candidate_targets),
                candidate_target,
            )
            repo_lock = _get_repo_dir_lock(candidate_target)
            lock_wait_start = time.time()
            with repo_lock:
                waited = time.time() - lock_wait_start
                logger.debug("Acquired clone lock for %s after %.3fs", candidate_target, waited)
                stage_dir = f"{candidate_target}.clone-{uuid.uuid4().hex[:8]}"
                logger.info("Cloning repository into staging path %s", stage_dir)
                _remove_existing_repo_dir(stage_dir)

                try:
                    _clone_repository(clone_source, stage_dir)
                    logger.debug("Clone into staging path completed: %s", stage_dir)
                    _remove_existing_repo_dir(candidate_target)
                    logger.debug(
                        "Promoting staged clone into final target (stage=%s, target=%s)",
                        stage_dir,
                        candidate_target,
                    )
                    _promote_staged_clone(stage_dir, candidate_target)
                    logger.info(
                        "Cloning completed in %.2fs (final path: %s)",
                        time.time() - start_time,
                        candidate_target,
                    )
                    return candidate_target
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "Clone attempt failed for target=%s stage=%s: %s",
                        candidate_target,
                        stage_dir,
                        exc,
                    )
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
                    logger.error("Clone workflow stopping after failure at target=%s", candidate_target)
                    break

        final_target = candidate_targets[-1] if short_target_dir else target_dir
        logger.error(
            "Repository clone failed after %.2fs (source=%s, final_target=%s, error=%s)",
            time.time() - start_time,
            _redact_clone_source_for_log(clone_source),
            final_target,
            last_error,
        )
        raise CloneRepositoryError(str(last_error), clone_source, final_target) from last_error
    else:
        logger.info("Source identified as local path: %s", source)
        if not os.path.exists(source) or not os.path.isdir(source):
            logger.error("Local repository source is invalid: %s", source)
            raise ValueError(f"Invalid local directory path: {source}")
        logger.info("Local repository source validated: %s", source)
        return source
