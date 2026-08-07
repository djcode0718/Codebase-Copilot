import os
import stat
import shutil
import git
import threading
import uuid
from urllib.parse import urlparse, quote
from app.config import REPOS_DIR
from app.utils.git_auth import get_git_auth_token
from app.utils.logger import get_logger
import time

logger = get_logger(__name__)

_REPO_DIR_LOCKS = {}
_REPO_DIR_LOCKS_GUARD = threading.Lock()


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

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def _build_authenticated_url(source: str) -> str:
    """Inject a GitHub token into HTTPS URL when available for private repos."""
    token = get_git_auth_token() or ""
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


def _clone_repository(source: str, target_dir: str) -> None:
    """Clone with non-interactive git settings to fail fast on auth issues."""
    clone_source = _build_authenticated_url(source)
    clone_env = os.environ.copy()
    clone_env["GIT_TERMINAL_PROMPT"] = "0"
    clone_env["GIT_ASKPASS"] = "echo"

    try:
        git.Repo.clone_from(clone_source, target_dir, env=clone_env)
    except git.exc.GitCommandError as e:
        err = str(e)
        lowered = err.lower()
        auth_signals = (
            "authentication failed",
            "could not read username",
            "access denied",
            "repository not found",
            "terminal prompts disabled",
        )
        if any(signal in lowered for signal in auth_signals):
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
        # Create a folder name from the repo url
        repo_name = source.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
            
        target_dir = os.path.join(REPOS_DIR, repo_name)
        repo_lock = _get_repo_dir_lock(target_dir)

        with repo_lock:
            _remove_existing_repo_dir(target_dir)
            logger.info(f"Cloning repository into {target_dir}")

            start_time = time.time()
            _clone_repository(source, target_dir)
            logger.info(f"Cloning completed in {time.time() - start_time:.2f}s")
        
        return target_dir
    else:
        logger.info(f"Source identified as local path: {source}")
        if not os.path.exists(source) or not os.path.isdir(source):
            raise ValueError(f"Invalid local directory path: {source}")
        return source
