import os
import re
import hashlib
from urllib.parse import urlparse


_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

_WINDOWS_RESERVED_PATTERN = re.compile(
    r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$",
    re.IGNORECASE,
)
_MAX_REPO_DIR_NAME = 64


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def normalize_clone_source(source: str) -> str:
    """Normalize clone source so browser-style URL query/fragment never reaches git clone."""
    raw_source = (source or "").strip()
    if not raw_source or not is_valid_url(raw_source):
        return raw_source

    parsed = urlparse(raw_source)
    if parsed.scheme not in {"http", "https"}:
        return raw_source

    return parsed._replace(params="", query="", fragment="").geturl()


def derive_repo_name(source: str) -> str:
    """Derive a filesystem-safe repository folder name from URL or local path."""
    raw_source = (source or "").strip()
    if not raw_source:
        return "repo"

    if is_valid_url(raw_source):
        parsed = urlparse(raw_source)
        candidate = (parsed.path or "").rstrip("/").split("/")[-1]
    else:
        candidate = os.path.basename(os.path.normpath(raw_source))

    if candidate.endswith('.git'):
        candidate = candidate[:-4]

    candidate = candidate.strip()
    candidate = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '-', candidate)
    candidate = re.sub(r'\s+', '-', candidate)
    candidate = candidate.rstrip(' .')

    if not candidate:
        candidate = "repo"

    if candidate.upper() in _WINDOWS_RESERVED_NAMES or _WINDOWS_RESERVED_PATTERN.match(candidate):
        candidate = f"{candidate}-repo"

    if len(candidate) > _MAX_REPO_DIR_NAME:
        digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:10]
        prefix_len = max(1, _MAX_REPO_DIR_NAME - len(digest) - 1)
        candidate = f"{candidate[:prefix_len]}-{digest}".rstrip(" .-") or "repo"

    return candidate
