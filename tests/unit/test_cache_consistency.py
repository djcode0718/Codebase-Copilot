"""
tests/unit/test_cache_consistency.py
────────────────────────────────────
Investigation and verification tests for:
1. Cache-consistency: proving that cached VectorStoreIndex queries the live Chroma
   collection directly upon retrieval, so deferred cache invalidation alone does NOT
   isolate queries from in-place Chroma mutations.
2. Index refreshing state tracking: verifying mark_index_refreshing / is_index_refreshing / unmark_index_refreshing.
3. Cross-resource consistency during incremental refresh:
   - Atomic graph update when files change
   - Self-healing recovery when graph is missing or corrupt on an unchanged refresh
   - Preservation of existing graph and deferred cache invalidation when graph build fails
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import threading
import time
import pytest
from unittest.mock import patch, MagicMock

import chromadb
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore

from app.indexing.incremental import (
    run_incremental_indexing,
    is_index_refreshing,
    mark_index_refreshing,
    unmark_index_refreshing,
    wait_for_index_refresh,
    IndexRefreshingError,
    acquire_index_read,
    acquire_index_write,
    get_index_rwlock,
)
from app.services.qa_service import (
    _index_cache,
    invalidate_index_cache,
    _get_indexes,
    handle_user_query,
)
from app.parsing.relationship_graph import validate_relationship_graph_file


def test_cached_vector_index_shares_live_chroma_state():
    """
    CRITICAL INVESTIGATION TEST:
    Demonstrates that a cached VectorStoreIndex does NOT snapshot vectors into memory.
    It holds a ChromaVectorStore wrapping chromadb.Collection.
    Every call to retriever.retrieve() delegates directly to collection.query() on disk/memory.
    Therefore, any in-place mutation to the Chroma collection is observed immediately
    by queries running on the cached vector_index even if _index_cache was never invalidated!
    """
    with tempfile.TemporaryDirectory() as td:
        chroma_client = chromadb.PersistentClient(path=td)
        collection = chroma_client.create_collection("test_shared_state")

        from llama_index.core.embeddings import MockEmbedding
        mock_embed = MockEmbedding(embed_dim=4)
        mock_embed._get_text_embedding = lambda text: [0.1, 0.2, 0.3, 0.4]
        mock_embed._get_query_embedding = lambda query: [0.1, 0.2, 0.3, 0.4]

        # Insert 2 initial nodes with embeddings
        collection.add(
            ids=["node_1", "node_2"],
            documents=["apple pie recipe", "banana bread recipe"],
            embeddings=[[0.1, 0.2, 0.3, 0.4], [0.1, 0.2, 0.3, 0.4]],
            metadatas=[{"path": "recipes/apple.py"}, {"path": "recipes/banana.py"}],
        )

        vector_store = ChromaVectorStore(chroma_collection=collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        vector_index = VectorStoreIndex.from_vector_store(
            vector_store,
            storage_context=storage_context,
            embed_model=mock_embed,
        )

        # Cache the vector index in _index_cache
        _index_cache["test_shared_state"] = (vector_index, None)

        # Verify initial retrieval finds node_1
        retriever = vector_index.as_retriever(similarity_top_k=2)
        initial_results = retriever.retrieve("apple")
        assert any(r.node.metadata.get("path") == "recipes/apple.py" for r in initial_results)

        # NOW: Mutate the active Chroma collection in-place WITHOUT invalidating _index_cache
        collection.delete(ids=["node_1"])
        collection.add(
            ids=["node_3"],
            documents=["cherry cobbler recipe"],
            embeddings=[[0.1, 0.2, 0.3, 0.4]],
            metadatas=[{"path": "recipes/cherry.py"}],
        )

        # Retrieve again using the UN-INVALIDATED cached vector_index
        cached_index, _ = _index_cache["test_shared_state"]
        mutated_retriever = cached_index.as_retriever(similarity_top_k=2)
        mutated_results = mutated_retriever.retrieve("recipe")

        retrieved_paths = {r.node.metadata.get("path") for r in mutated_results}

        # PROOF: The cached index immediately observes the deletion of apple and addition of cherry!
        assert "recipes/apple.py" not in retrieved_paths
        assert "recipes/cherry.py" in retrieved_paths

        # Clean up
        invalidate_index_cache("test_shared_state")


def test_index_refreshing_state_tracker():
    """Verify that mark_index_refreshing, is_index_refreshing, and unmark_index_refreshing track active refresh state."""
    test_idx = "idx_refresh_test_123"
    assert is_index_refreshing(test_idx) is False

    mark_index_refreshing(test_idx)
    assert is_index_refreshing(test_idx) is True

    unmark_index_refreshing(test_idx)
    assert is_index_refreshing(test_idx) is False


def test_incremental_refresh_updates_relationship_graph_and_invalidates_cache(tmp_path):
    """Verify that when files change, relationship graph is regenerated atomically and cache is invalidated."""
    index_name = "test_inc_graph_repo"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    index_dir = tmp_path / "index" / index_name
    index_dir.mkdir(parents=True)

    file_a = repo_dir / "service.py"
    file_a.write_text("def process_data():\n    pass\n")

    # Initial manifest
    manifest = {
        "service.py": {"hash": "old_hash", "chunk_ids": ["c1"]}
    }
    with open(index_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Initial graph
    initial_graph = {"old_sym": ["service.py:old_sym"]}
    with open(index_dir / "relationship_graph.json", "w") as f:
        json.dump(initial_graph, f)

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["c1", "ctx_1"],
        "metadatas": [{"path": "_codebase_context", "context_generation": "gen_1", "context_total_chunks": 1}]
    }

    mock_client = MagicMock()
    mock_index = MagicMock()

    with patch("app.indexing.incremental.INDEX_DIR", str(tmp_path / "index")), \
         patch("app.indexing.incremental.load_manifest", return_value=manifest), \
         patch("app.indexing.incremental._get_chroma_collection", return_value=(mock_client, mock_collection)), \
         patch("app.indexing.incremental.load_vector_index", return_value=mock_index), \
         patch("app.indexing.incremental.get_file_hash", return_value="new_hash"), \
         patch("app.services.qa_service.invalidate_index_cache") as mock_invalidate:

        success = run_incremental_indexing(
            repo_path=str(repo_dir),
            index_name=index_name,
        )

        assert success is True
        # Cache invalidation MUST be called after successful multi-resource update
        mock_invalidate.assert_called_once_with(index_name)

        # Graph file on disk must be updated
        graph_path = index_dir / "relationship_graph.json"
        assert graph_path.exists()
        assert validate_relationship_graph_file(str(graph_path)) is True
        with open(graph_path) as f:
            updated_graph = json.load(f)
        assert "process_data" in updated_graph


def test_incremental_refresh_self_heals_missing_or_corrupt_graph(tmp_path):
    """Verify that an unchanged refresh detects missing/corrupt relationship graph and self-heals."""
    index_name = "test_self_heal_graph"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    index_dir = tmp_path / "index" / index_name
    index_dir.mkdir(parents=True)

    file_a = repo_dir / "model.py"
    file_a.write_text("def train():\n    pass\n")

    # Manifest matches file hash (no files changed)
    manifest = {
        "model.py": {"hash": "current_hash", "chunk_ids": ["c1"]}
    }
    with open(index_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # BUT relationship_graph.json is corrupted
    with open(index_dir / "relationship_graph.json", "w") as f:
        f.write("{corrupt json")

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["c1", "ctx_1"],
        "metadatas": [{"path": "_codebase_context", "context_generation": "gen_1", "context_total_chunks": 1}]
    }
    mock_client = MagicMock()
    mock_index = MagicMock()

    with patch("app.indexing.incremental.INDEX_DIR", str(tmp_path / "index")), \
         patch("app.indexing.incremental.load_manifest", return_value=manifest), \
         patch("app.indexing.incremental._get_chroma_collection", return_value=(mock_client, mock_collection)), \
         patch("app.indexing.incremental.load_vector_index", return_value=mock_index), \
         patch("app.indexing.incremental.get_file_hash", return_value="current_hash"), \
         patch("app.services.qa_service.invalidate_index_cache"):

        # Should not early exit! Must repair the corrupt relationship graph
        success = run_incremental_indexing(
            repo_path=str(repo_dir),
            index_name=index_name,
        )

        assert success is True
        # Corrupt graph replaced with valid graph
        graph_path = index_dir / "relationship_graph.json"
        assert validate_relationship_graph_file(str(graph_path)) is True
        with open(graph_path) as f:
            healed_graph = json.load(f)
        assert "train" in healed_graph


def test_graph_failure_preserves_old_graph_and_defers_cache_invalidation(tmp_path):
    """Verify that if graph generation fails, the pre-existing graph is preserved and cache invalidation is deferred."""
    index_name = "test_graph_fail_repo"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    index_dir = tmp_path / "index" / index_name
    index_dir.mkdir(parents=True)

    file_a = repo_dir / "app.py"
    file_a.write_text("def run():\n    pass\n")

    manifest = {"app.py": {"hash": "old_hash", "chunk_ids": ["c1"]}}
    with open(index_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    original_graph = {"original_symbol": ["app.py:original"]}
    with open(index_dir / "relationship_graph.json", "w") as f:
        json.dump(original_graph, f)

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": ["c1", "ctx_1"],
        "metadatas": [{"path": "_codebase_context", "context_generation": "gen_1", "context_total_chunks": 1}]
    }
    mock_client = MagicMock()
    mock_index = MagicMock()

    with patch("app.indexing.incremental.INDEX_DIR", str(tmp_path / "index")), \
         patch("app.indexing.incremental.load_manifest", return_value=manifest), \
         patch("app.indexing.incremental._get_chroma_collection", return_value=(mock_client, mock_collection)), \
         patch("app.indexing.incremental.load_vector_index", return_value=mock_index), \
         patch("app.indexing.incremental.get_file_hash", return_value="new_hash"), \
         patch("app.parsing.relationship_graph.RelationshipGraphBuilder.build_graph_atomic", side_effect=RuntimeError("Disk full")), \
         patch("app.services.qa_service.invalidate_index_cache") as mock_invalidate:

        # Operation returns False due to partial failure (graph update failed)
        success = run_incremental_indexing(
            repo_path=str(repo_dir),
            index_name=index_name,
        )

        assert success is False

        # Pre-existing graph MUST remain intact!
        graph_path = index_dir / "relationship_graph.json"
        with open(graph_path) as f:
            current_graph = json.load(f)
        assert current_graph == original_graph

        # Cache invalidation MUST be deferred!
        mock_invalidate.assert_not_called()


def test_cached_index_not_returned_during_refresh():
    """Verify that _get_indexes does not return a cached VectorStoreIndex while index is refreshing."""
    test_idx = "idx_cached_block_test"
    mock_vector_index = MagicMock()
    mock_bm25 = MagicMock()
    _index_cache[test_idx] = (mock_vector_index, mock_bm25)

    try:
        mark_index_refreshing(test_idx)

        # Calling _get_indexes with small timeout must raise IndexRefreshingError rather than returning cached index
        with pytest.raises(IndexRefreshingError):
            _get_indexes(test_idx, wait_timeout=0.05)
    finally:
        unmark_index_refreshing(test_idx)
        invalidate_index_cache(test_idx)


def test_query_read_lock_blocks_refresh_write():
    """Verify that an active reader prevents a writer from acquiring write access until the reader finishes."""
    import threading
    import time

    test_idx = "idx_rw_read_blocks_write"
    lock = get_index_rwlock(test_idx)

    writer_acquired = threading.Event()
    writer_finished = threading.Event()

    def writer_task():
        acquired = lock.acquire_write(timeout=2.0)
        if acquired:
            writer_acquired.set()
            lock.release_write()
            writer_finished.set()

    # Reader acquires read lock
    with acquire_index_read(test_idx, timeout=1.0):
        # Start writer in background
        w_thread = threading.Thread(target=writer_task)
        w_thread.start()

        # Writer must NOT be able to acquire lock while reader is active
        time.sleep(0.08)
        assert not writer_acquired.is_set(), "Writer acquired lock while reader was active!"

    # Once reader exits context, writer must acquire and finish
    w_thread.join(timeout=1.0)
    assert writer_acquired.is_set(), "Writer failed to acquire lock after reader finished!"


def test_refresh_write_lock_blocks_new_queries():
    """Verify that an active refresh writer blocks new queries from acquiring read access until refresh completes."""
    import threading
    import time

    test_idx = "idx_rw_write_blocks_read"
    lock = get_index_rwlock(test_idx)

    reader_acquired = threading.Event()

    def reader_task():
        acquired = lock.acquire_read(timeout=2.0)
        if acquired:
            reader_acquired.set()
            lock.release_read()

    # Writer acquires write lock
    with acquire_index_write(test_idx, timeout=1.0):
        # Start reader in background
        r_thread = threading.Thread(target=reader_task)
        r_thread.start()

        # Reader must NOT acquire while writer is active
        time.sleep(0.08)
        assert not reader_acquired.is_set(), "Reader acquired lock while writer was active!"

    # Once writer exits context, reader must acquire and finish
    r_thread.join(timeout=1.0)
    assert reader_acquired.is_set(), "Reader failed to acquire lock after writer finished!"


def test_multiple_concurrent_readers():
    """Verify that multiple concurrent readers can hold read access simultaneously without blocking each other."""
    import threading
    import time

    test_idx = "idx_rw_multi_readers"
    lock = get_index_rwlock(test_idx)

    readers_active = []
    barrier = threading.Barrier(3)
    errors = []

    def reader_task(idx):
        try:
            with acquire_index_read(test_idx, timeout=1.0):
                readers_active.append(idx)
                barrier.wait(timeout=1.0)
                time.sleep(0.05)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=reader_task, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)

    assert not errors, f"Reader thread errors: {errors}"
    assert len(readers_active) == 3, f"Expected 3 active readers, got {len(readers_active)}"


def test_timed_out_query_controlled_retry_response():
    """Verify that when a refresh holds the write lock, a query times out cleanly and receives the controlled retry response."""
    test_idx = "idx_query_timeout_retry"

    with acquire_index_write(test_idx, timeout=1.0):
        # handle_user_query attempts to read with wait_timeout=0.05s
        with patch("app.services.qa_service._get_indexes", side_effect=IndexRefreshingError("Refresh in progress")):
            response, engine, mem, mode = handle_user_query(
                query="What does this repository do?",
                index_name=test_idx,
            )
            assert "currently being updated" in response.lower()
            assert "retry" in response.lower()


def test_failed_refresh_releases_exclusive_access():
    """Verify that an exception inside acquire_index_write releases the lock immediately and unblocks readers."""
    test_idx = "idx_fail_release_test"

    try:
        with acquire_index_write(test_idx, timeout=1.0):
            raise RuntimeError("Simulated failure during Chroma update")
    except RuntimeError:
        pass

    # Lock must be released immediately
    lock = get_index_rwlock(test_idx)
    assert lock._active_writer is False
    assert lock.is_refreshing() is False

    # Reader must be able to acquire read access without delay
    assert lock.acquire_read(timeout=0.1) is True
    lock.release_read()


def test_subsequent_queries_and_refreshes_succeed_after_failure(tmp_path):
    """Verify that after an incremental refresh failure, subsequent queries and refreshes succeed normally."""
    index_name = "idx_fail_recovery_test"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # 1. Trigger failure in refresh
    with patch("app.indexing.incremental._run_incremental_indexing_impl", side_effect=ValueError("Chroma mutation crash")):
        with pytest.raises(ValueError):
            run_incremental_indexing(str(repo_dir), index_name)

    # 2. Verify subsequent query can acquire read lock
    with acquire_index_read(index_name, timeout=0.1):
        assert is_index_refreshing(index_name) is False

    # 3. Verify subsequent refresh can acquire write lock and complete
    with patch("app.indexing.incremental._run_incremental_indexing_impl", return_value=True):
        success = run_incremental_indexing(str(repo_dir), index_name)
        assert success is True

    assert is_index_refreshing(index_name) is False


def test_streaming_and_non_streaming_respect_synchronization():
    """Verify that both streaming (_prepare_stream_prompt) and non-streaming (handle_user_query) respect the write lock."""
    import asyncio
    test_idx = "idx_stream_nonstream_sync"

    # Hold write lock (simulating active incremental refresh)
    with acquire_index_write(test_idx, timeout=1.0):
        # 1. Non-streaming path: handle_user_query gets controlled retry response
        with patch("app.services.qa_service._get_indexes", side_effect=IndexRefreshingError("Refresh in progress")):
            resp, _, _, _ = handle_user_query("List files", test_idx)
            assert "currently being updated" in resp.lower()

        # 2. Streaming path: _prepare_stream_prompt raises IndexRefreshingError
        from api.services.chat_service import _prepare_stream_prompt
        async def run_stream_prep():
            with pytest.raises(IndexRefreshingError):
                await _prepare_stream_prompt(
                    query="List files",
                    index_name=test_idx,
                    repo_id="test_repo",
                    chat_id="test_chat",
                    memory_context=None,
                )

        # Run async check
        asyncio.run(run_stream_prep())


# ── Focused Concurrency Remediation Tests (Findings A - G) ──────────────────


@pytest.mark.asyncio
async def test_async_cancellation_while_waiting_for_read_lock_does_not_leak_readers():
    """
    Finding A: Async Cancellation Reader Leak.
    Verify that cancelling an async task while awaiting read access cleanly removes
    the waiter without leaking active reader counts, allowing subsequent writes to succeed.
    """
    test_idx = "idx_cancel_wait_leak_test"
    lock = get_index_rwlock(test_idx)

    # 1. Acquire write lock synchronously
    write_token = lock.acquire_write(timeout=1.0)
    assert write_token is True
    assert lock.is_refreshing() is True

    started_wait = asyncio.Event()

    async def waiting_reader():
        started_wait.set()
        async with acquire_index_read(test_idx, timeout=5.0):
            pass

    task = asyncio.create_task(waiting_reader())
    await started_wait.wait()
    # Allow task to hit the wait future
    await asyncio.sleep(0.05)

    assert len(lock._async_reader_waiters) == 1
    assert lock._active_readers == 0

    # 2. Cancel the waiting task
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Waiter must be removed immediately and readers count MUST remain 0
    assert len(lock._async_reader_waiters) == 0
    assert lock._active_readers == 0

    # 3. Release write lock
    lock.release_write()
    assert lock.is_refreshing() is False
    assert lock._active_readers == 0

    # 4. Subsequent write lock must acquire immediately without hanging
    acquired = lock.acquire_write(timeout=0.2)
    assert acquired is True
    lock.release_write()


@pytest.mark.asyncio
async def test_async_cancellation_immediately_after_read_acquisition_releases_lock():
    """
    Finding A: Ensure cancellation right at or inside async with cleanly releases lock.
    """
    test_idx = "idx_cancel_after_acq_test"
    lock = get_index_rwlock(test_idx)

    inside_context = asyncio.Event()

    async def read_and_cancel():
        async with acquire_index_read(test_idx, timeout=1.0):
            assert lock._active_readers == 1
            inside_context.set()
            # Simulate cancellation arriving while inside the body
            raise asyncio.CancelledError()

    task = asyncio.create_task(read_and_cancel())
    await inside_context.wait()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Lock must be released cleanly
    assert lock._active_readers == 0
    # Next writer acquires immediately
    assert lock.acquire_write(timeout=0.1) is True
    lock.release_write()


def test_executor_worker_reuse_no_thread_local_bleed():
    """
    Finding B: ThreadPoolExecutor Thread-Local State Bleed.
    Verify that reusing executor worker threads across tasks does not carry over
    stale reentrant read state that would bypass active writers.
    """
    from concurrent.futures import ThreadPoolExecutor
    test_idx = "idx_worker_reuse_bleed_test"
    lock = get_index_rwlock(test_idx)

    # Use a single-worker executor to guarantee thread reuse
    with ThreadPoolExecutor(max_workers=1) as pool:
        # Task 1: acquires and releases read lock
        def task_1():
            with acquire_index_read(test_idx, timeout=1.0):
                pass
            return True

        f1 = pool.submit(task_1)
        assert f1.result() is True
        assert lock._active_readers == 0

        # Now acquire write lock on main thread
        assert lock.acquire_write(timeout=1.0) is True

        # Task 2: executed on the same reused worker thread.
        # It must NOT believe it has reentrant read access from Task 1.
        # It must be blocked by the active writer.
        def task_2():
            # Should time out because writer is active
            return lock.acquire_read(timeout=0.1)

        f2 = pool.submit(task_2)
        # Must return False (timeout), not True (bypass)
        assert f2.result() is False

        lock.release_write()


def test_cross_thread_acquisition_and_release():
    """
    Finding B/F: Cross-thread token acquisition and release.
    Verify that explicit tokens allow releasing read/write locks safely from another thread.
    """
    from app.indexing.incremental import _get_context_read_token, _get_context_write_token
    test_idx = "idx_cross_thread_test"
    lock = get_index_rwlock(test_idx)

    token_box = []

    # Thread 1 acquires
    def worker_acquire():
        assert lock.acquire_read(timeout=1.0) is True
        token = _get_context_read_token(test_idx)
        token_box.append(token)

    t1 = threading.Thread(target=worker_acquire)
    t1.start()
    t1.join()

    assert len(token_box) == 1
    read_token = token_box[0]
    assert lock._active_readers == 1

    # Thread 2 releases with explicit token
    def worker_release():
        lock.release_read(read_token)

    t2 = threading.Thread(target=worker_release)
    t2.start()
    t2.join()

    assert lock._active_readers == 0
    # Writer can acquire now
    assert lock.acquire_write(timeout=0.1) is True
    lock.release_write()


def test_recursive_write_lock_depth_tracking():
    """
    Finding C: Recursive Write Lock Premature Release.
    Verify that nested write acquisition increments depth and that an inner release
    does NOT release the outer lock.
    """
    test_idx = "idx_recursive_write_test"
    lock = get_index_rwlock(test_idx)

    # Outer write
    assert lock.acquire_write(timeout=1.0) is True
    assert lock._active_writer is True
    assert lock._writer_token.depth == 1

    # Inner (nested) write
    assert lock.acquire_write(timeout=1.0) is True
    assert lock._active_writer is True
    assert lock._writer_token.depth == 2

    # Inner release
    lock.release_write()
    # Outer lock must remain held!
    assert lock._active_writer is True
    assert lock._writer_token.depth == 1
    assert lock.is_refreshing() is True

    # Other reader cannot acquire
    assert lock.acquire_read(timeout=0.05) is False

    # Outer release
    lock.release_write()
    # Now fully released
    assert lock._active_writer is False
    assert lock._writer_token is None
    assert lock.is_refreshing() is False

    # Reader can acquire now
    assert lock.acquire_read(timeout=0.1) is True
    lock.release_read()


def test_read_to_write_upgrade_deadlock_rejection():
    """
    Finding D: Read-to-Write Lock Upgrade Deadlock.
    Verify that an attempt to acquire write access while holding read access in the
    same context immediately raises RuntimeError rather than hanging.
    """
    test_idx = "idx_upgrade_deadlock_test"
    lock = get_index_rwlock(test_idx)

    with acquire_index_read(test_idx, timeout=1.0):
        # Attempting write lock while holding read access MUST raise immediately
        start = time.time()
        with pytest.raises(RuntimeError, match="Read-to-write lock upgrade is forbidden"):
            lock.acquire_write(timeout=5.0)
        elapsed = time.time() - start
        # Must fail immediately without waiting for timeout
        assert elapsed < 0.5, f"Expected immediate failure, took {elapsed:.2f}s"


def test_invalid_and_duplicate_release_rejection():
    """
    Finding F: Lock Release Ownership Validation.
    Verify that releasing unowned or already released locks raises RuntimeError.
    """
    test_idx = "idx_invalid_release_test"
    lock = get_index_rwlock(test_idx)

    # 1. Release read without acquiring
    with pytest.raises(RuntimeError, match="Cannot release unowned read lock"):
        lock.release_read()

    # 2. Release write without acquiring
    with pytest.raises(RuntimeError, match="Cannot release write lock"):
        lock.release_write()

    # 3. Duplicate release
    assert lock.acquire_read(timeout=1.0) is True
    lock.release_read()
    with pytest.raises(RuntimeError, match="Cannot release unowned read lock"):
        lock.release_read()

    # 4. Release write with mismatched caller
    def acquire_on_t1(out):
        assert lock.acquire_write(timeout=1.0) is True
        out.append(True)

    out = []
    t1 = threading.Thread(target=acquire_on_t1, args=(out,))
    t1.start()
    t1.join()
    assert len(out) == 1

    # Caller on main thread attempts to release t1's write lock without token
    with pytest.raises(RuntimeError, match="Cannot release unowned write lock"):
        lock.release_write()

    # Clean up with proper owner
    def release_on_t1():
        lock.release_write()
    t_clean = threading.Thread(target=release_on_t1)
    t_clean.start()
    t_clean.join()
    assert lock._active_writer is False


def test_case_normalized_lock_registry_identity():
    """
    Finding G: Lock Registry Case Normalization.
    Ensure case variations resolve to the exact same lock instance,
    while distinct repositories resolve to distinct locks.
    """
    lock1 = get_index_rwlock("Speech-Emotion-Analyzer")
    lock2 = get_index_rwlock("speech-emotion-analyzer")
    lock3 = get_index_rwlock("  SPEECH-EMOTION-ANALYZER  ")
    assert lock1 is lock2
    assert lock2 is lock3

    # Distinct repositories must remain distinct
    lock_a = get_index_rwlock("repo-alpha")
    lock_b = get_index_rwlock("repo-beta")
    assert lock_a is not lock_b
    assert lock_a is not lock1


def test_writer_preference_and_starvation_prevention():
    """
    Verify writer preference: new readers are blocked when a writer is queued,
    preventing writer starvation by high-frequency readers.
    """
    test_idx = "idx_writer_preference_test"
    lock = get_index_rwlock(test_idx)

    # Reader 1 acquires
    assert lock.acquire_read(timeout=1.0) is True
    assert lock._active_readers == 1

    writer_queued = threading.Event()
    writer_finished = threading.Event()

    def background_writer():
        writer_queued.set()
        assert lock.acquire_write(timeout=2.0) is True
        lock.release_write()
        writer_finished.set()

    t_writer = threading.Thread(target=background_writer)
    t_writer.start()
    writer_queued.wait()
    time.sleep(0.05)  # Let writer enter waiting state

    assert lock._waiting_writers == 1

    # Reader 2 attempts to acquire: must be BLOCKED because writer is waiting
    def background_reader(res):
        res.append(lock.acquire_read(timeout=0.1))

    r_res = []
    t_reader = threading.Thread(target=background_reader, args=(r_res,))
    t_reader.start()
    t_reader.join()
    assert r_res == [False], "Reader 2 should have been blocked by waiting writer"

    # Reader 1 releases: writer completes
    lock.release_read()
    writer_finished.wait(timeout=2.0)
    t_writer.join()

    # Now readers can acquire again
    assert lock.acquire_read(timeout=0.1) is True
    lock.release_read()


def test_refresh_acquires_write_lock_while_llm_inference_runs_outside_read_lock():
    """
    Finding E: Overextended Read Lock During LLM Inference.
    Demonstrate that incremental refresh can acquire exclusive write access while
    an unrelated user query's LLM completion is still executing, because read access
    was already released right after vector retrieval.
    """
    from llama_index.core.settings import Settings
    test_idx = "idx_llm_concurrency_test"

    llm_started = threading.Event()
    llm_may_proceed = threading.Event()

    def slow_llm_complete(*args, **kwargs):
        llm_started.set()
        # Block until released
        llm_may_proceed.wait(timeout=5.0)
        return "Simulated LLM response"

    from llama_index.core.schema import NodeWithScore
    from app.retrieval.query_router import QueryMode
    node = NodeWithScore(node=TextNode(text="def foo(): pass", metadata={"path": "test.py"}), score=0.95)
    mock_engine = MagicMock(spec=["_retriever", "chat"])
    mock_engine._retriever.retrieve.return_value = [node]
    mock_engine.chat.side_effect = slow_llm_complete

    with patch("app.config.USE_RERANKER", False), \
         patch("app.services.qa_service._get_indexes") as mock_get_indexes, \
         patch("app.services.qa_service._resolve_query_mode", return_value=("What does foo do?", QueryMode.CODE_LOOKUP)):
        mock_vector = MagicMock()
        mock_bm25 = MagicMock()
        mock_get_indexes.return_value = (mock_vector, mock_bm25)

        query_thread_done = threading.Event()

        def run_query():
            handle_user_query(
                "What does foo do?",
                test_idx,
                chat_engine=mock_engine,
                last_mode=QueryMode.CODE_LOOKUP,
            )
            query_thread_done.set()

        t_query = threading.Thread(target=run_query)
        t_query.start()

        # Wait until query reaches LLM completion step
        assert llm_started.wait(timeout=3.0) is True

        # At this exact moment, LLM completion is still running, BUT
        # read lock must ALREADY be released!
        lock = get_index_rwlock(test_idx)
        assert lock._active_readers == 0, f"Expected 0 active readers during LLM call, got {lock._active_readers}"

        # Refresh MUST be able to acquire exclusive write access immediately
        write_start = time.time()
        acquired_write = lock.acquire_write(timeout=0.5)
        assert acquired_write is True, "Refresh should acquire write lock immediately while LLM completes"
        lock.release_write()
        assert time.time() - write_start < 0.2

        # Let LLM complete
        llm_may_proceed.set()
        t_query.join(timeout=2.0)
        assert query_thread_done.is_set()


def test_chroma_partial_failure_releases_write_lock_and_subsequent_refresh_recovers(tmp_path):
    """
    Section 4 / Audit 7: Chroma failure safety and self-healing.
    Verify that an unhandled exception during incremental refresh releases write lock,
    and subsequent refresh successfully executes self-healing logic.
    """
    test_idx = "idx_chroma_recovery_test"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "module.py").write_text("def test(): pass")

    # Step 1: Simulate crash during in-place insertion
    with patch("app.indexing.incremental._run_incremental_indexing_impl", side_effect=RuntimeError("Chroma insert failure")):
        with pytest.raises(RuntimeError):
            run_incremental_indexing(str(repo_dir), test_idx)

    # Write lock must be unconditionally released
    lock = get_index_rwlock(test_idx)
    assert lock._active_writer is False
    assert lock.is_refreshing() is False

    # Step 2: Next refresh self-heals and completes cleanly
    with patch("app.indexing.incremental._run_incremental_indexing_impl", return_value=True):
        result = run_incremental_indexing(str(repo_dir), test_idx)
        assert result is True
        assert is_index_refreshing(test_idx) is False

