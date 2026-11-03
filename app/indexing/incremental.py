import os
import json
import hashlib
import time
import uuid
import threading
import contextvars
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional, Any
from llama_index.core import Document
from app.config import INDEX_DIR
from app.ingestion.file_filter import filter_files
from app.parsing.code_parser import load_documents, parse_documents
from app.indexing.index_builder import load_vector_index, _get_chroma_collection
from app.ingestion.git_history import load_git_history_for_file
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IndexRefreshingError(RuntimeError):
    """Raised when an index cannot be read because it is actively undergoing mutation."""
    pass


@dataclass
class ReadToken:
    token_id: str
    index_name: str
    owner_id: str
    depth: int = 1


@dataclass
class WriteToken:
    token_id: str
    index_name: str
    owner_id: str
    depth: int = 1


_read_tokens_var: contextvars.ContextVar[Optional[Dict[str, ReadToken]]] = contextvars.ContextVar(
    "_read_tokens_var", default=None
)
_write_tokens_var: contextvars.ContextVar[Optional[Dict[str, WriteToken]]] = contextvars.ContextVar(
    "_write_tokens_var", default=None
)


def _canonicalize_index_name(index_name: str) -> str:
    return (index_name or "").strip().lower()


def _get_current_owner_id() -> str:
    try:
        import asyncio
        task = asyncio.current_task()
        if task is not None:
            return f"task-{id(task)}"
    except Exception:
        pass
    return f"thread-{threading.get_ident()}"


def _get_context_read_token(index_name: str) -> Optional[ReadToken]:
    c_name = _canonicalize_index_name(index_name)
    tokens = _read_tokens_var.get()
    if tokens is None:
        return None
    return tokens.get(c_name)


def _set_context_read_token(token: ReadToken) -> None:
    c_name = _canonicalize_index_name(token.index_name)
    tokens = _read_tokens_var.get()
    if tokens is None:
        tokens = {}
        _read_tokens_var.set(tokens)
    tokens[c_name] = token


def _remove_context_read_token(index_name: str) -> None:
    c_name = _canonicalize_index_name(index_name)
    tokens = _read_tokens_var.get()
    if tokens is not None:
        tokens.pop(c_name, None)


def _get_context_write_token(index_name: str) -> Optional[WriteToken]:
    c_name = _canonicalize_index_name(index_name)
    tokens = _write_tokens_var.get()
    if tokens is None:
        return None
    return tokens.get(c_name)


def _set_context_write_token(token: WriteToken) -> None:
    c_name = _canonicalize_index_name(token.index_name)
    tokens = _write_tokens_var.get()
    if tokens is None:
        tokens = {}
        _write_tokens_var.set(tokens)
    tokens[c_name] = token


def _remove_context_write_token(index_name: str) -> None:
    c_name = _canonicalize_index_name(index_name)
    tokens = _write_tokens_var.get()
    if tokens is not None:
        tokens.pop(c_name, None)


class IndexRWLock:
    """
    Coordinated Readers-Writer lock per repository index.
    - Multiple concurrent readers permitted across threads and asyncio coroutines.
    - Writers have exclusive access.
    - Writer preference to prevent writer starvation: when a writer is waiting,
      new readers will wait unless already holding reentrant read access in the current context.
    - Token-based ownership tracking and ContextVar isolation: prevents ThreadPoolExecutor
      worker reuse state bleed.
    - Async cancellation safe: waiters queue with asyncio futures; cancellation while waiting
      removes the waiter without leaking reader counts.
    - Read-to-write upgrade rejection: immediately raises RuntimeError on upgrade attempts
      rather than deadlocking.
    - Reentrant write tracking: maintains write depth so inner release does not unlock outer.
    - Strict release validation: rejects invalid or unowned release calls.
    """

    def __init__(self, index_name: str):
        self.index_name = _canonicalize_index_name(index_name)
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._active_readers = 0
        self._waiting_writers = 0
        self._active_writer = False
        self._writer_owner_id: Optional[str] = None
        self._writer_token: Optional[WriteToken] = None
        self._active_read_tokens: Dict[str, ReadToken] = {}
        # Async waiters: (loop, future, owner_id)
        self._async_reader_waiters: List[Tuple[Any, Any, str]] = []
        self._async_writer_waiters: List[Tuple[Any, Any, str]] = []

    def _notify_next_waiters_locked(self) -> None:
        """Must be called while holding self._lock."""
        if self._waiting_writers > 0:
            self._cond.notify_all()
            while self._async_writer_waiters:
                loop, fut, _ = self._async_writer_waiters.pop(0)
                if not fut.done():
                    loop.call_soon_threadsafe(fut.set_result, None)
                    break
        else:
            self._cond.notify_all()
            while self._async_reader_waiters:
                loop, fut, _ = self._async_reader_waiters.pop(0)
                if not fut.done():
                    loop.call_soon_threadsafe(fut.set_result, None)

    def acquire_read(self, timeout: float = 5.0) -> bool:
        # Reentrant check: if this context already holds a read token, increment depth
        existing = _get_context_read_token(self.index_name)
        if existing is not None:
            existing.depth += 1
            return True

        start = time.time()
        owner_id = _get_current_owner_id()
        with self._lock:
            while self._active_writer or self._waiting_writers > 0:
                remaining = timeout - (time.time() - start)
                if remaining <= 0:
                    logger.warning(
                        "Timed out waiting for read access on index '%s' (active_writer=%s, waiting_writers=%d)",
                        self.index_name,
                        self._active_writer,
                        self._waiting_writers,
                    )
                    return False
                self._cond.wait(timeout=remaining)

            self._active_readers += 1
            token = ReadToken(
                token_id=uuid.uuid4().hex,
                index_name=self.index_name,
                owner_id=owner_id,
                depth=1,
            )
            self._active_read_tokens[token.token_id] = token
            _set_context_read_token(token)
            return True

    def release_read(self, token: Optional[ReadToken] = None) -> None:
        if token is None:
            token = _get_context_read_token(self.index_name)
        if token is None:
            raise RuntimeError(
                f"Cannot release unowned read lock for index '{self.index_name}': no active read token found in context."
            )

        if _canonicalize_index_name(token.index_name) != self.index_name:
            raise RuntimeError(
                f"Cannot release read lock: token index '{token.index_name}' does not match lock index '{self.index_name}'."
            )

        if token.depth > 1:
            token.depth -= 1
            return

        with self._lock:
            if token.token_id not in self._active_read_tokens:
                raise RuntimeError(
                    f"Cannot release read lock for index '{self.index_name}': token '{token.token_id}' not found in active tokens."
                )
            del self._active_read_tokens[token.token_id]
            self._active_readers = max(0, self._active_readers - 1)
            _remove_context_read_token(self.index_name)
            if self._active_readers == 0:
                self._notify_next_waiters_locked()

    async def acquire_read_async(self, timeout: float = 5.0) -> bool:
        existing = _get_context_read_token(self.index_name)
        if existing is not None:
            existing.depth += 1
            return True

        import asyncio
        loop = asyncio.get_running_loop()
        owner_id = _get_current_owner_id()
        start_time = loop.time()

        while True:
            waiter_entry = None
            with self._lock:
                if not self._active_writer and self._waiting_writers == 0:
                    self._active_readers += 1
                    token = ReadToken(
                        token_id=uuid.uuid4().hex,
                        index_name=self.index_name,
                        owner_id=owner_id,
                        depth=1,
                    )
                    self._active_read_tokens[token.token_id] = token
                    _set_context_read_token(token)
                    return True

                elapsed = loop.time() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    logger.warning(
                        "Timed out waiting for async read access on index '%s' (active_writer=%s, waiting_writers=%d)",
                        self.index_name,
                        self._active_writer,
                        self._waiting_writers,
                    )
                    return False

                fut = loop.create_future()
                waiter_entry = (loop, fut, owner_id)
                self._async_reader_waiters.append(waiter_entry)

            try:
                await asyncio.wait_for(asyncio.shield(fut), timeout=remaining)
            except asyncio.TimeoutError:
                with self._lock:
                    if waiter_entry is not None and waiter_entry in self._async_reader_waiters:
                        self._async_reader_waiters.remove(waiter_entry)
                logger.warning(
                    "Timed out waiting for async read access on index '%s' (active_writer=%s, waiting_writers=%d)",
                    self.index_name,
                    self._active_writer,
                    self._waiting_writers,
                )
                return False
            except (asyncio.CancelledError, Exception):
                with self._lock:
                    if waiter_entry is not None and waiter_entry in self._async_reader_waiters:
                        self._async_reader_waiters.remove(waiter_entry)
                raise

    def acquire_write(self, timeout: float = 60.0) -> bool:
        # Detect read-to-write upgrade attempt: forbid immediately to prevent deadlock
        if _get_context_read_token(self.index_name) is not None:
            raise RuntimeError(
                f"Read-to-write lock upgrade is forbidden on index '{self.index_name}' (deadlock hazard). "
                "Release read access before requesting write access."
            )

        start = time.time()
        owner_id = _get_current_owner_id()
        with self._lock:
            if self._active_writer and self._writer_owner_id == owner_id:
                if self._writer_token is not None:
                    self._writer_token.depth += 1
                    return True

            self._waiting_writers += 1
            try:
                while self._active_writer or self._active_readers > 0:
                    remaining = timeout - (time.time() - start)
                    if remaining <= 0:
                        logger.warning(
                            "Timed out waiting for write access on index '%s' (active_readers=%d, active_writer=%s)",
                            self.index_name,
                            self._active_readers,
                            self._active_writer,
                        )
                        return False
                    self._cond.wait(timeout=remaining)

                self._active_writer = True
                self._writer_owner_id = owner_id
                token = WriteToken(
                    token_id=uuid.uuid4().hex,
                    index_name=self.index_name,
                    owner_id=owner_id,
                    depth=1,
                )
                self._writer_token = token
                _set_context_write_token(token)
                logger.info("Acquired exclusive write lock for index '%s'", self.index_name)
                return True
            finally:
                self._waiting_writers = max(0, self._waiting_writers - 1)

    def release_write(self, token: Optional[WriteToken] = None) -> None:
        owner_id = _get_current_owner_id()
        with self._lock:
            if not self._active_writer or self._writer_token is None:
                raise RuntimeError(
                    f"Cannot release write lock for index '{self.index_name}': no active writer."
                )

            active_tok = self._writer_token
            if token is not None:
                if token.token_id != active_tok.token_id:
                    raise RuntimeError(
                        f"Cannot release write lock for index '{self.index_name}': token mismatch ('{token.token_id}' != '{active_tok.token_id}')."
                    )
            else:
                if self._writer_owner_id != owner_id:
                    raise RuntimeError(
                        f"Cannot release unowned write lock for index '{self.index_name}': caller '{owner_id}' is not lock owner '{self._writer_owner_id}'."
                    )

            if active_tok.depth > 1:
                active_tok.depth -= 1
                logger.debug(
                    "Decremented reentrant write depth for index '%s' to %d",
                    self.index_name,
                    active_tok.depth,
                )
                return

            self._active_writer = False
            self._writer_owner_id = None
            self._writer_token = None
            _remove_context_write_token(self.index_name)
            self._notify_next_waiters_locked()
            logger.info("Released exclusive write lock for index '%s' and notified waiters", self.index_name)

    async def acquire_write_async(self, timeout: float = 60.0) -> bool:
        if _get_context_read_token(self.index_name) is not None:
            raise RuntimeError(
                f"Read-to-write lock upgrade is forbidden on index '{self.index_name}' (deadlock hazard). "
                "Release read access before requesting write access."
            )

        import asyncio
        loop = asyncio.get_running_loop()
        owner_id = _get_current_owner_id()
        start_time = loop.time()

        while True:
            waiter_entry = None
            with self._lock:
                if self._active_writer and self._writer_owner_id == owner_id:
                    if self._writer_token is not None:
                        self._writer_token.depth += 1
                        return True

                if not self._active_writer and self._active_readers == 0:
                    self._active_writer = True
                    self._writer_owner_id = owner_id
                    token = WriteToken(
                        token_id=uuid.uuid4().hex,
                        index_name=self.index_name,
                        owner_id=owner_id,
                        depth=1,
                    )
                    self._writer_token = token
                    _set_context_write_token(token)
                    logger.info("Acquired exclusive write lock for index '%s'", self.index_name)
                    return True

                elapsed = loop.time() - start_time
                remaining = timeout - elapsed
                if remaining <= 0:
                    logger.warning(
                        "Timed out waiting for async write access on index '%s' (active_readers=%d, active_writer=%s)",
                        self.index_name,
                        self._active_readers,
                        self._active_writer,
                    )
                    return False

                self._waiting_writers += 1
                fut = loop.create_future()
                waiter_entry = (loop, fut, owner_id)
                self._async_writer_waiters.append(waiter_entry)

            try:
                await asyncio.wait_for(asyncio.shield(fut), timeout=remaining)
            except asyncio.TimeoutError:
                with self._lock:
                    if waiter_entry is not None and waiter_entry in self._async_writer_waiters:
                        self._async_writer_waiters.remove(waiter_entry)
                    self._waiting_writers = max(0, self._waiting_writers - 1)
                logger.warning(
                    "Timed out waiting for async write access on index '%s' (active_readers=%d, active_writer=%s)",
                    self.index_name,
                    self._active_readers,
                    self._active_writer,
                )
                return False
            except (asyncio.CancelledError, Exception):
                with self._lock:
                    if waiter_entry is not None and waiter_entry in self._async_writer_waiters:
                        self._async_writer_waiters.remove(waiter_entry)
                    self._waiting_writers = max(0, self._waiting_writers - 1)
                raise
            else:
                with self._lock:
                    self._waiting_writers = max(0, self._waiting_writers - 1)

    def is_refreshing(self) -> bool:
        with self._lock:
            return self._active_writer or self._waiting_writers > 0


_index_locks: Dict[str, IndexRWLock] = {}
_global_locks_mutex = threading.Lock()


def get_index_rwlock(index_name: str) -> IndexRWLock:
    canonical_name = _canonicalize_index_name(index_name)
    with _global_locks_mutex:
        if canonical_name not in _index_locks:
            _index_locks[canonical_name] = IndexRWLock(canonical_name)
        return _index_locks[canonical_name]


class _IndexReadContext:
    def __init__(self, lock: IndexRWLock, index_name: str, timeout: float):
        self.lock = lock
        self.index_name = index_name
        self.timeout = timeout
        self.token: Optional[ReadToken] = None

    def __enter__(self):
        acquired = self.lock.acquire_read(timeout=self.timeout)
        if not acquired:
            raise IndexRefreshingError(
                f"Index '{self.index_name}' is currently undergoing incremental refresh. "
                "Reads are paused to prevent retrieving partially updated vectors."
            )
        self.token = _get_context_read_token(self.lock.index_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            self.lock.release_read(self.token)
            self.token = None
        else:
            self.lock.release_read()

    async def __aenter__(self):
        acquired = False
        try:
            acquired = await self.lock.acquire_read_async(timeout=self.timeout)
            if not acquired:
                raise IndexRefreshingError(
                    f"Index '{self.index_name}' is currently undergoing incremental refresh. "
                    "Reads are paused to prevent retrieving partially updated vectors."
                )
            self.token = _get_context_read_token(self.lock.index_name)
            return self
        except BaseException:
            if acquired:
                tok = self.token or _get_context_read_token(self.lock.index_name)
                if tok is not None:
                    self.lock.release_read(tok)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            self.lock.release_read(self.token)
            self.token = None
        else:
            self.lock.release_read()


class _IndexWriteContext:
    def __init__(self, lock: IndexRWLock, index_name: str, timeout: float):
        self.lock = lock
        self.index_name = index_name
        self.timeout = timeout
        self.token: Optional[WriteToken] = None

    def __enter__(self):
        acquired = self.lock.acquire_write(timeout=self.timeout)
        if not acquired:
            raise IndexRefreshingError(
                f"Could not acquire exclusive write access for index '{self.index_name}' within {self.timeout}s."
            )
        self.token = _get_context_write_token(self.lock.index_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            self.lock.release_write(self.token)
            self.token = None
        else:
            self.lock.release_write()

    async def __aenter__(self):
        acquired = False
        try:
            acquired = await self.lock.acquire_write_async(timeout=self.timeout)
            if not acquired:
                raise IndexRefreshingError(
                    f"Could not acquire exclusive write access for index '{self.index_name}' within {self.timeout}s."
                )
            self.token = _get_context_write_token(self.lock.index_name)
            return self
        except BaseException:
            if acquired:
                tok = self.token or _get_context_write_token(self.lock.index_name)
                if tok is not None:
                    self.lock.release_write(tok)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            self.lock.release_write(self.token)
            self.token = None
        else:
            self.lock.release_write()


def acquire_index_read(index_name: str, timeout: float = 5.0) -> _IndexReadContext:
    """Acquire shared read access for index_name (supports sync 'with' and async 'async with')."""
    lock = get_index_rwlock(index_name)
    return _IndexReadContext(lock, index_name, timeout)


def acquire_index_write(index_name: str, timeout: float = 60.0) -> _IndexWriteContext:
    """Acquire exclusive write access for index_name (supports sync 'with' and async 'async with')."""
    lock = get_index_rwlock(index_name)
    return _IndexWriteContext(lock, index_name, timeout)


def is_index_refreshing(index_name: str) -> bool:
    """Return True if index_name is currently undergoing active mutation/refresh."""
    return get_index_rwlock(index_name).is_refreshing()


_refreshing_write_tokens: Dict[str, WriteToken] = {}
_refreshing_tokens_lock = threading.Lock()


def mark_index_refreshing(index_name: str) -> None:
    """Mark index_name as actively undergoing mutation."""
    canonical_name = _canonicalize_index_name(index_name)
    lock = get_index_rwlock(canonical_name)
    acquired = lock.acquire_write()
    if acquired:
        token = _get_context_write_token(canonical_name)
        if token is not None:
            with _refreshing_tokens_lock:
                _refreshing_write_tokens[canonical_name] = token


def unmark_index_refreshing(index_name: str) -> None:
    """Unmark index_name after mutation finishes or fails, and notify waiting readers."""
    canonical_name = _canonicalize_index_name(index_name)
    lock = get_index_rwlock(canonical_name)
    token = None
    with _refreshing_tokens_lock:
        token = _refreshing_write_tokens.pop(canonical_name, None)
    lock.release_write(token)


def wait_for_index_refresh(index_name: str, timeout: float = 5.0) -> bool:
    """Wait for in-flight refresh to finish."""
    lock = get_index_rwlock(index_name)
    start = time.time()
    with lock._lock:
        while lock._active_writer or lock._waiting_writers > 0:
            remaining = timeout - (time.time() - start)
            if remaining <= 0:
                return False
            lock._cond.wait(timeout=remaining)
        return True


def get_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def load_manifest(index_name: str) -> Dict[str, Dict]:
    """Load manifest.json for a given index with fallback recovery."""
    manifest_dir = os.path.join(INDEX_DIR, index_name)
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    tmp_path = os.path.join(manifest_dir, "manifest.json.tmp")

    if not os.path.exists(manifest_path) and os.path.exists(tmp_path):
        try:
            os.replace(tmp_path, manifest_path)
        except Exception:
            pass

    if not os.path.exists(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load manifest: {e}")
        if os.path.exists(tmp_path):
            try:
                with open(tmp_path, "r", encoding="utf-8") as tf:
                    return json.load(tf)
            except Exception:
                pass
        return {}


def save_manifest(index_name: str, manifest: Dict[str, Dict]):
    """Save manifest.json for a given index atomically."""
    manifest_dir = os.path.join(INDEX_DIR, index_name)
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    tmp_path = os.path.join(manifest_dir, "manifest.json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, manifest_path)
    except Exception as e:
        logger.warning(f"Failed to save manifest: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def build_initial_manifest(nodes: List, repo_path: str, index_name: str):
    """Build and save initial manifest.json during full build."""
    manifest = {}
    for node in nodes:
        rel_path = node.metadata.get("path")
        if not rel_path or rel_path == "_codebase_context":
            continue
        abs_path = os.path.join(repo_path, rel_path)
        if os.path.exists(abs_path):
            file_hash = get_file_hash(abs_path)
            manifest.setdefault(rel_path, {"hash": file_hash, "chunk_ids": []})["chunk_ids"].append(node.node_id)
    save_manifest(index_name, manifest)


import threading

_active_staging_builds: Set[str] = set()
_staging_builds_lock = threading.Lock()


def register_active_staging_build(staging_collection_name: str) -> None:
    """Thread-safe registration of an actively writing staging collection name."""
    if staging_collection_name:
        with _staging_builds_lock:
            _active_staging_builds.add(staging_collection_name)
        logger.debug(f"Registered active staging build: {staging_collection_name}")


def unregister_active_staging_build(staging_collection_name: str) -> None:
    """Thread-safe unregistration of an active staging collection name once finished or aborted."""
    if staging_collection_name:
        with _staging_builds_lock:
            _active_staging_builds.discard(staging_collection_name)
        logger.debug(f"Unregistered active staging build: {staging_collection_name}")


def get_active_staging_builds() -> Set[str]:
    """Return a thread-safe snapshot copy of currently active staging build collection names."""
    with _staging_builds_lock:
        return set(_active_staging_builds)


def _safely_cleanup_obsolete_staging(
    index_name: str,
    client,
    collection,
    manifest: Dict[str, Dict],
    current_repo_id: Optional[str] = None,
    current_source: Optional[str] = None,
    active_staging_builds: Optional[Set[str]] = None,
    repo_path: Optional[str] = None,
) -> None:
    """
    Safely delete obsolete staging collections associated with index_name.

    Strict safety conditions:
    1. Identify staging collections matching '{index_name}_stage_*'.
    2. Confirm active collection contains ALL expected manifest chunk IDs.
    3. Confirm active collection contains _codebase_context.
    4. Confirm staging collection is not in-flight or actively being written to:
       - Fails safe if tracking sets are unavailable.
       - Skips cleanup if a different repository is indexing.
       - Skips cleanup if another concurrent operation for the same repository/source is active.
       - Skips deletion of any candidate collection that is in an active staging build.
       - Only proceeds when the current refresh is the sole in-flight operation.
    5. Confirm no required vectors exist ONLY in staging.
    6. Only delete verified obsolete staging collections; never touch backup directories.
    """
    if not client or not hasattr(client, "list_collections"):
        return

    try:
        staging_prefix = f"{index_name}_stage_"
        all_collections = client.list_collections()
        staging_cols = [
            c for c in all_collections
            if getattr(c, "name", "").startswith(staging_prefix)
        ]
        if not staging_cols:
            return

        # Condition 2: Confirm active collection has all expected manifest chunk IDs
        all_expected_ids = {
            cid
            for file_entry in manifest.values()
            for cid in file_entry.get("chunk_ids", [])
        }
        active_records = collection.get(include=[]) if hasattr(collection, "get") else {}
        active_ids = set()
        if isinstance(active_records, dict):
            active_ids = set(active_records.get("ids", []))
        elif hasattr(active_records, "get"):
            raw_act = active_records.get("ids", [])
            active_ids = set(raw_act) if isinstance(raw_act, (list, set)) else set()

        if all_expected_ids and not all_expected_ids.issubset(active_ids):
            missing_ids = all_expected_ids - active_ids
            logger.warning(
                f"Skipping staging cleanup for {index_name}: active collection is missing "
                f"{len(missing_ids)} expected manifest vectors."
            )
            return

        # Condition 3: Confirm active collection contains _codebase_context
        ctx_records = collection.get(where={"path": "_codebase_context"}) if hasattr(collection, "get") else {}
        ctx_ids = []
        if isinstance(ctx_records, dict):
            ctx_ids = ctx_records.get("ids", [])
        elif hasattr(ctx_records, "get"):
            raw_ctx = ctx_records.get("ids", [])
            ctx_ids = raw_ctx if isinstance(raw_ctx, (list, set)) else []

        if not ctx_ids:
            logger.warning(
                f"Skipping staging cleanup for {index_name}: active collection lacks _codebase_context."
            )
            return

        # Condition 4: Concurrency & in-flight safety check
        try:
            from api.services import indexing_service
            in_flight_repos = getattr(indexing_service, "_indexing_in_flight", None)
            in_flight_sources = getattr(indexing_service, "_indexing_sources_in_flight", None)
        except Exception as e:
            logger.warning(
                f"Skipping staging cleanup for {index_name}: in-flight tracking information is unavailable ({e})."
            )
            return

        # Fail safe if tracking information is completely unavailable
        if in_flight_repos is None or in_flight_sources is None:
            logger.warning(
                f"Skipping staging cleanup for {index_name}: in-flight tracking sets are not available."
            )
            return

        # Helper to distinguish remote URLs from local filesystem paths
        def _is_url(s: str) -> bool:
            s = (s or "").strip().lower()
            return (
                s.startswith("http://")
                or s.startswith("https://")
                or s.startswith("git@")
                or s.startswith("ssh://")
                or s.startswith("git://")
            )

        def _norm_src(s: str) -> str:
            s = (s or "").strip()
            if not s:
                return ""
            if _is_url(s):
                s = s.lower()
                if s.endswith(".git"):
                    s = s[:-4]
                return s.rstrip("/")
            # Local filesystem path
            try:
                return os.path.realpath(os.path.abspath(s)).lower().rstrip(os.sep)
            except Exception:
                return s.lower().rstrip("/\\")

        # Resolve current operation identity if not explicitly passed
        resolved_source = current_source
        resolved_repo_id = current_repo_id

        if not resolved_source and repo_path and os.path.exists(repo_path):
            local_candidate = _norm_src(repo_path)
            remote_candidate = None
            try:
                import git
                r = git.Repo(repo_path)
                if r.remotes and hasattr(r.remotes, "origin") and r.remotes.origin.url:
                    remote_candidate = _norm_src(r.remotes.origin.url)
            except Exception:
                pass

            norm_inflight = {_norm_src(s): s for s in (in_flight_sources or set())}
            if local_candidate in norm_inflight:
                resolved_source = local_candidate
            elif remote_candidate and remote_candidate in norm_inflight:
                resolved_source = remote_candidate
            elif local_candidate:
                resolved_source = local_candidate
            elif remote_candidate:
                resolved_source = remote_candidate

        norm_curr_src = _norm_src(resolved_source) if resolved_source else None

        # Check if in-flight tracking is empty vs active
        if in_flight_sources or in_flight_repos:
            # If tracking sets are active, we must be able to reliably identify our current operation
            if not norm_curr_src and not resolved_repo_id:
                logger.warning(
                    f"Skipping staging cleanup for {index_name}: current refresh operation identity "
                    f"(repo_id/source) is not provided; cannot distinguish current refresh from concurrent operations."
                )
                return

            # Check if a DIFFERENT repository is indexing in-flight
            other_sources = set()
            if norm_curr_src:
                for src in in_flight_sources:
                    if _norm_src(src) != norm_curr_src:
                        other_sources.add(src)
            elif in_flight_sources:
                other_sources = set(in_flight_sources)

            if other_sources:
                logger.warning(
                    f"Skipping staging cleanup for {index_name}: a different repository is indexing in-flight: {other_sources}"
                )
                return

            # Check if another operation for the SAME repository/source is active
            if resolved_repo_id and in_flight_repos:
                other_repo_ids = {rid for rid in in_flight_repos if str(rid) != str(resolved_repo_id)}
                if other_repo_ids:
                    logger.warning(
                        f"Skipping staging cleanup for {index_name}: concurrent operation for same repository in-flight: {other_repo_ids}"
                    )
                    return
            elif len(in_flight_repos) > 1 or len(in_flight_sources) > 1:
                logger.warning(
                    f"Skipping staging cleanup for {index_name}: multiple in-flight operations active ({len(in_flight_repos)} repos, {len(in_flight_sources)} sources)."
                )
                return

        # Combine active staging builds tracking (registry is primary protection)
        active_builds = set(active_staging_builds) if active_staging_builds is not None else set()
        active_builds.update(get_active_staging_builds())

        # Evaluate each staging collection for safe deletion
        for stg in staging_cols:
            stg_name = getattr(stg, "name", "")

            # Primary protection: active staging build registry
            if stg_name in active_builds:
                logger.warning(
                    f"Skipping deletion of {stg_name}: staging build is actively registered in-flight."
                )
                continue

            # Conservative fallback: protect collections with recent activity (within indexing timeout 300s)
            stg_dir = os.path.join(INDEX_DIR, stg_name)
            if os.path.exists(stg_dir):
                try:
                    import time
                    if time.time() - os.path.getmtime(stg_dir) < 300.0:
                        logger.warning(
                            f"Skipping deletion of {stg_name}: staging directory was modified recently (<300s fallback window)."
                        )
                        continue
                except Exception:
                    pass

            stg_records = stg.get(include=["metadatas"]) if hasattr(stg, "get") else {}
            stg_ids = set()
            if isinstance(stg_records, dict):
                stg_ids = set(stg_records.get("ids", []))
            elif hasattr(stg_records, "get"):
                raw_stg = stg_records.get("ids", [])
                stg_ids = set(raw_stg) if isinstance(raw_stg, (list, set)) else set()

            # Condition 5: Confirm no required vectors exist ONLY in staging
            orphaned_required = stg_ids.intersection(all_expected_ids) - active_ids
            if orphaned_required:
                logger.warning(
                    f"Skipping deletion of {stg_name}: contains {len(orphaned_required)} "
                    f"required vectors not yet present in active collection."
                )
                continue

            # Safe to delete this specific verified obsolete staging collection
            logger.info(f"Safely purging verified obsolete staging collection: {stg_name}")
            try:
                client.delete_collection(stg_name)
            except Exception as del_err:
                logger.warning(f"Could not delete staging collection {stg_name}: {del_err}")

            # Clean up disk staging directory if it exists, never touching backups
            if os.path.exists(stg_dir) and not stg_dir.endswith(".backup") and "backup" not in stg_name.lower():
                import shutil
                shutil.rmtree(stg_dir, ignore_errors=True)
                logger.info(f"Removed obsolete staging directory: {stg_dir}")

    except Exception as cleanup_err:
        logger.warning(f"Error during safe staging cleanup for {index_name}: {cleanup_err}", exc_info=True)


def run_incremental_indexing(
    repo_path: str,
    index_name: str,
    current_repo_id: Optional[str] = None,
    current_source: Optional[str] = None,
    active_staging_builds: Optional[Set[str]] = None,
) -> bool:
    """
    Run incremental (diff-based) reindexing with active vector presence validation,
    codebase context maintenance, atomic relationship graph regeneration, and safe staging collection cleanup.
    Returns True if update occurred, False otherwise (indicating full build required or partial refresh).
    """
    mark_index_refreshing(index_name)
    try:
        return _run_incremental_indexing_impl(
            repo_path=repo_path,
            index_name=index_name,
            current_repo_id=current_repo_id,
            current_source=current_source,
            active_staging_builds=active_staging_builds,
        )
    finally:
        unmark_index_refreshing(index_name)


def _run_incremental_indexing_impl(
    repo_path: str,
    index_name: str,
    current_repo_id: Optional[str] = None,
    current_source: Optional[str] = None,
    active_staging_builds: Optional[Set[str]] = None,
) -> bool:
    manifest = load_manifest(index_name)
    if not manifest:
        logger.info(f"No manifest found for {index_name}. Incremental re-indexing fallback to full build.")
        return False

    logger.info(f"Running incremental re-indexing for {index_name}")
    valid_files = filter_files(repo_path)

    current_files = {os.path.abspath(fp): os.path.relpath(fp, repo_path) for fp in valid_files}
    manifest_files = {os.path.abspath(os.path.join(repo_path, fp)): fp for fp in manifest.keys()}

    index = load_vector_index(index_name)
    client, collection = _get_chroma_collection(index_name)

    # 1. Retrieve active vector IDs from Chroma collection
    active_ids = set()
    active_ids_queried = False
    if hasattr(collection, "get"):
        try:
            active_records = collection.get(include=[])
            if isinstance(active_records, dict):
                active_ids = set(active_records.get("ids", []))
                active_ids_queried = True
            elif hasattr(active_records, "get"):
                raw_act = active_records.get("ids", [])
                active_ids = set(raw_act) if isinstance(raw_act, (list, set)) else set()
                active_ids_queried = True
        except Exception as e:
            logger.warning(f"Could not query active IDs from collection {index_name}: {e}")

    # 2. Check if _codebase_context exists in the active collection and verify consistency
    context_ids = []
    context_metadatas = []
    if hasattr(collection, "get"):
        try:
            ctx_records = collection.get(
                where={"path": "_codebase_context"},
                include=["metadatas"]
            )
            if isinstance(ctx_records, dict):
                context_ids = ctx_records.get("ids", [])
                context_metadatas = ctx_records.get("metadatas", []) or []
            elif hasattr(ctx_records, "get"):
                raw_ctx = ctx_records.get("ids", [])
                context_ids = raw_ctx if isinstance(raw_ctx, (list, set)) else []
                raw_meta = ctx_records.get("metadatas", [])
                context_metadatas = raw_meta if isinstance(raw_meta, list) else []
        except Exception as e:
            logger.warning(f"Could not query _codebase_context IDs from collection {index_name}: {e}")

    context_missing = (len(context_ids) == 0)

    # Reliable context consistency check using generation metadata & docstore sync
    context_inconsistent = False
    if not context_missing:
        # Group by context_generation
        generations = set()
        gen_chunk_counts = {}
        for m in context_metadatas:
            if isinstance(m, dict):
                g = m.get("context_generation")
                if g:
                    generations.add(g)
                    gen_chunk_counts[g] = gen_chunk_counts.get(g, 0) + 1

        # Multiple generations indicate a previous failed old-context deletion
        if len(generations) > 1:
            logger.warning(
                f"Detected {len(generations)} multiple codebase context generations in {index_name}: {generations}. Reconciling context."
            )
            context_inconsistent = True
        elif len(generations) == 1:
            single_gen = next(iter(generations))
            expected_total = None
            for m in context_metadatas:
                if isinstance(m, dict) and m.get("context_generation") == single_gen:
                    expected_total = m.get("context_total_chunks")
                    if expected_total is not None:
                        break
            # Check if there are stray nodes not belonging to this generation
            if len(context_ids) != gen_chunk_counts.get(single_gen, 0):
                logger.warning(
                    f"Context contains {len(context_ids)} nodes but generation {single_gen} has {gen_chunk_counts.get(single_gen)}. Reconciling context."
                )
                context_inconsistent = True
            elif expected_total is not None and gen_chunk_counts.get(single_gen) != expected_total:
                logger.warning(
                    f"Context generation {single_gen} has {gen_chunk_counts.get(single_gen)} chunks, expected {expected_total}. Reconciling context."
                )
                context_inconsistent = True
        elif len(context_ids) > 1:
            # Legacy context without generation metadata but with multiple nodes: duplicate/stale
            logger.warning(
                f"Multiple legacy context nodes detected without generation metadata in {index_name}. Reconciling context."
            )
            context_inconsistent = True

        # Check Chroma vs docstore consistency
        if not context_inconsistent and hasattr(index, "docstore") and hasattr(index.docstore, "get_document"):
            for cid in context_ids:
                try:
                    if not index.docstore.get_document(cid, raise_error=False):
                        logger.warning(f"Context node {cid} exists in Chroma but is missing from docstore. Reconciling context.")
                        context_inconsistent = True
                        break
                except Exception:
                    pass

    # 2.5 Check if relationship_graph.json exists and is valid on disk
    graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
    from app.parsing.relationship_graph import validate_relationship_graph_file, RelationshipGraphBuilder
    graph_inconsistent = not os.path.exists(graph_path) or not validate_relationship_graph_file(graph_path)

    # 3. Detect additions, deletions, modifications, and missing-vector files
    added_abs = set(current_files.keys()) - set(manifest_files.keys())
    deleted_abs = set(manifest_files.keys()) - set(current_files.keys())

    modified_abs = set()
    for abs_path in set(current_files.keys()) & set(manifest_files.keys()):
        rel_path = current_files[abs_path]
        current_hash = get_file_hash(abs_path)
        manifest_hash = manifest[rel_path].get("hash", "")
        expected_chunk_ids = manifest[rel_path].get("chunk_ids", [])

        content_changed = (current_hash != manifest_hash)
        missing_chunk_ids = [cid for cid in expected_chunk_ids if cid not in active_ids]
        vectors_missing = bool(
            active_ids_queried
            and (
                missing_chunk_ids
                or (not expected_chunk_ids and os.path.exists(abs_path) and os.path.getsize(abs_path) > 0)
            )
        )

        if content_changed or vectors_missing:
            if vectors_missing and not content_changed:
                logger.info(f"Unchanged file '{rel_path}' is missing expected vectors in active Chroma; scheduling re-ingestion.")
            modified_abs.add(abs_path)

    files_changed = bool(added_abs or deleted_abs or modified_abs)
    if not files_changed and not context_missing and not context_inconsistent and not graph_inconsistent:
        logger.info("No files added, deleted, or modified, and active index is consistent.")
        _safely_cleanup_obsolete_staging(
            index_name,
            client,
            collection,
            manifest,
            current_repo_id=current_repo_id,
            current_source=current_source,
            active_staging_builds=active_staging_builds,
            repo_path=repo_path,
        )
        return True

    # 4. Load existing git history dictionary
    git_history_path = os.path.join(INDEX_DIR, index_name, "git_history.json")
    git_history_dict = {}
    if os.path.exists(git_history_path):
        try:
            with open(git_history_path, "r", encoding="utf-8") as f:
                git_data = json.load(f)
            for fp, items in git_data.items():
                git_history_dict[fp] = [
                    Document(
                        text=item["text"],
                        metadata=item["metadata"],
                        excluded_embed_metadata_keys=["doc_type", "chunk_index"]
                    )
                    for item in items
                ]
        except Exception as ge:
            logger.warning(f"Failed to load git history: {ge}")

    # 5. Process deletions and existing chunks for modified files
    node_ids_to_delete = []
    for abs_path in deleted_abs | modified_abs:
        rel_path = None
        for k in list(manifest.keys()):
            if os.path.abspath(os.path.join(repo_path, k)) == abs_path:
                rel_path = k
                break
        if rel_path and rel_path in manifest:
            chunk_ids = manifest[rel_path].get("chunk_ids", [])
            node_ids_to_delete.extend(chunk_ids)
            if abs_path in deleted_abs:
                del manifest[rel_path]
                git_history_dict.pop(rel_path, None)

    if node_ids_to_delete:
        logger.info(f"Deleting {len(node_ids_to_delete)} old nodes from Chroma and docstore")
        try:
            collection.delete(ids=node_ids_to_delete)
        except Exception as e:
            logger.warning(f"Failed to delete old nodes from Chroma: {e}")
        try:
            if hasattr(index, "docstore"):
                for nid in node_ids_to_delete:
                    index.docstore.delete_document(nid, raise_error=False)
        except Exception as e:
            logger.warning(f"Failed to delete old nodes from docstore: {e}")

    # 6. Process additions / modifications (including missing-vector files)
    for abs_path in added_abs | modified_abs:
        rel_path = current_files[abs_path]
        logger.info(f"Re-indexing file: {rel_path}")

        try:
            docs = load_documents([abs_path], repo_path)
            nodes = parse_documents(docs)
            if nodes:
                index.insert_nodes(nodes)
                chunk_ids = [node.node_id for node in nodes]
                manifest[rel_path] = {
                    "hash": get_file_hash(abs_path),
                    "chunk_ids": chunk_ids
                }
        except Exception as e:
            logger.warning(f"Failed to re-index {rel_path}: {e}")

        try:
            git_docs = load_git_history_for_file(abs_path, repo_path)
            if git_docs:
                git_history_dict[rel_path] = git_docs
        except Exception as ge:
            logger.warning(f"Failed to update git history for {rel_path}: {ge}")

    # 7. Maintain _codebase_context failure-safely (generate & validate first, insert, then clean obsolete)
    if files_changed or context_missing or context_inconsistent:
        new_node_ids = set()
        try:
            from app.indexing.context_builder import build_codebase_context
            from llama_index.core.node_parser import SentenceSplitter

            # Step 1: Generate replacement context document first
            context_doc = build_codebase_context(valid_files, repo_path, index_name)

            # Step 2: Split it into nodes
            context_splitter = SentenceSplitter(chunk_size=768, chunk_overlap=64)
            replacement_nodes = context_splitter.get_nodes_from_documents([context_doc])

            # Step 3: Validate replacement nodes before any mutation
            if not replacement_nodes:
                raise ValueError("Codebase context splitting yielded 0 nodes.")

            context_gen_id = f"ctx_gen_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            total_chunks = len(replacement_nodes)
            for idx, node in enumerate(replacement_nodes):
                node.metadata["context_generation"] = context_gen_id
                node.metadata["context_chunk_index"] = idx
                node.metadata["context_total_chunks"] = total_chunks
                node.metadata["path"] = "_codebase_context"

            new_node_ids = {node.node_id for node in replacement_nodes}

            # Step 4: Insert replacement nodes into active index BEFORE deleting old context
            index.insert_nodes(replacement_nodes)
            logger.info(f"Inserted {len(replacement_nodes)} replacement codebase context nodes into active index.")

            # Step 5: Once insertion succeeds, remove obsolete context nodes from Chroma and docstore
            obsolete_context_ids = [cid for cid in context_ids if cid not in new_node_ids]
            if obsolete_context_ids:
                try:
                    collection.delete(ids=obsolete_context_ids)
                except Exception as ce:
                    logger.warning(f"Failed to delete obsolete context nodes from Chroma: {ce}")
                if hasattr(index, "docstore"):
                    for cid in obsolete_context_ids:
                        try:
                            index.docstore.delete_document(cid, raise_error=False)
                        except Exception:
                            pass
        except Exception as ctx_err:
            logger.warning(f"Failed to maintain codebase context during incremental indexing: {ctx_err}", exc_info=True)
            # If insertion failed midway, rollback any newly inserted nodes so old context remains clean
            if new_node_ids:
                try:
                    collection.delete(ids=list(new_node_ids))
                except Exception:
                    pass
                if hasattr(index, "docstore"):
                    for nid in new_node_ids:
                        try:
                            index.docstore.delete_document(nid, raise_error=False)
                        except Exception:
                            pass

    # 8. Update relationship graph atomically
    graph_updated = True
    if files_changed or graph_inconsistent:
        try:
            graph_builder = RelationshipGraphBuilder(repo_path)
            graph_dir = os.path.join(INDEX_DIR, index_name)
            graph, final_graph_path = graph_builder.build_graph_atomic(valid_files, graph_dir)
            logger.info(f"Updated relationship graph atomically for {index_name} at {final_graph_path}")
        except Exception as ge:
            logger.warning(
                f"Failed to update relationship graph atomically for {index_name}: {ge}. "
                "Preserving existing relationship graph.",
                exc_info=True,
            )
            graph_updated = False

    # 9. Save manifest
    save_manifest(index_name, manifest)

    # 10. Save updated git history
    from app.ingestion.git_history import save_git_history_dict
    save_git_history_dict(git_history_dict, index_name)

    # 11. Safely clean up obsolete staging collections if safety conditions are satisfied
    _safely_cleanup_obsolete_staging(
        index_name,
        client,
        collection,
        manifest,
        current_repo_id=current_repo_id,
        current_source=current_source,
        active_staging_builds=active_staging_builds,
        repo_path=repo_path,
    )

    # 12. Invalidate in-memory cache only after successful multi-resource update
    if graph_updated:
        try:
            from app.services.qa_service import invalidate_index_cache
            invalidate_index_cache(index_name)
        except Exception as ie:
            logger.warning(f"Failed to invalidate index cache for {index_name}: {ie}")
    else:
        logger.warning(
            f"Partial refresh completed for {index_name}: vectors and context updated, "
            f"but relationship graph update failed. Index cache invalidation deferred."
        )

    logger.info("Incremental re-indexing complete.")
    return graph_updated
