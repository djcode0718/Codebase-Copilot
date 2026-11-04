"""
Regression tests for B7: Non-destructive repository refresh.

Validates:
- Existing clone and index are never destroyed before new index is validated.
- Clone failure leaves existing repository and index intact.
- Indexing/embedding failure leaves existing working index intact and cleans staging artifacts.
- Staged index validation and atomic promotion.
- Interrupted refresh handling preserving prior index.
- Concurrent refresh requests do not corrupt each other.
"""
from __future__ import annotations
import os
import shutil
import tempfile
import threading
import uuid
import pytest
from unittest.mock import MagicMock, patch

from api.services.indexing_service import (
    _validate_staged_index,
    _promote_staged_index,
    _run_pipeline_sync,
)
from api.routers.repo import _get_refresh_lock, _REFRESH_LOCKS


def test_validate_staged_index_success(tmp_path):
    """Valid staged index with chroma sqlite and manifest passes validation."""
    staging_dir = tmp_path / "test_repo_stage"
    chroma_dir = staging_dir / "chroma"
    chroma_dir.mkdir(parents=True)
    sqlite_file = chroma_dir / "chroma.sqlite3"
    sqlite_file.write_bytes(b"SQLite format 3\x00 fake data")
    manifest_file = staging_dir / "manifest.json"
    manifest_file.write_text('{"file.py": {"chunk_ids": ["c1"]}}')

    assert _validate_staged_index(str(staging_dir), min_nodes=1) is True


def test_validate_staged_index_missing_chroma(tmp_path):
    """Staged index missing chroma directory raises ValueError."""
    staging_dir = tmp_path / "test_repo_stage"
    staging_dir.mkdir()
    manifest_file = staging_dir / "manifest.json"
    manifest_file.write_text("{}")

    with pytest.raises(ValueError, match="Chroma directory missing"):
        _validate_staged_index(str(staging_dir), min_nodes=1)


def test_validate_staged_index_empty_sqlite(tmp_path):
    """Staged index with empty chroma.sqlite3 raises ValueError."""
    staging_dir = tmp_path / "test_repo_stage"
    chroma_dir = staging_dir / "chroma"
    chroma_dir.mkdir(parents=True)
    sqlite_file = chroma_dir / "chroma.sqlite3"
    sqlite_file.write_bytes(b"")  # 0 bytes

    with pytest.raises(ValueError, match="chroma.sqlite3 missing or empty"):
        _validate_staged_index(str(staging_dir), min_nodes=1)


def test_promote_staged_index_atomic_swap(tmp_path, monkeypatch):
    """Promoting staged index swaps it into the target directory atomically."""
    import app.config as config
    monkeypatch.setattr(config, "INDEX_DIR", str(tmp_path))

    target_dir = tmp_path / "my_repo"
    target_dir.mkdir()
    (target_dir / "version.txt").write_text("v1_original")

    staging_dir = tmp_path / "my_repo_stage_123"
    staging_dir.mkdir()
    (staging_dir / "version.txt").write_text("v2_new")

    _promote_staged_index("my_repo_stage_123", "my_repo")

    # Target directory now has new version
    assert (target_dir / "version.txt").read_text() == "v2_new"
    # Staging directory is gone
    assert not staging_dir.exists()


def test_promote_staged_index_rollback_on_failure(tmp_path, monkeypatch):
    """If promotion fails midway, original index directory is restored."""
    import app.config as config
    monkeypatch.setattr(config, "INDEX_DIR", str(tmp_path))

    target_dir = tmp_path / "my_repo"
    target_dir.mkdir()
    (target_dir / "version.txt").write_text("v1_original")

    staging_dir = tmp_path / "my_repo_stage_123"
    staging_dir.mkdir()
    (staging_dir / "version.txt").write_text("v2_new")

    original_replace = os.replace
    call_count = [0]

    def failing_replace(src, dst):
        call_count[0] += 1
        # First replace moves final_dir to backup_dir -> allow
        if call_count[0] == 1:
            return original_replace(src, dst)
        # Second replace moves staging_dir to final_dir -> simulate filesystem crash
        if call_count[0] == 2:
            raise OSError("Disk I/O error during replace")
        # Third replace restores backup_dir to final_dir -> allow
        return original_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="Disk I/O error"):
        _promote_staged_index("my_repo_stage_123", "my_repo")

    # Original directory must have been restored by rollback
    assert target_dir.exists()
    assert (target_dir / "version.txt").read_text() == "v1_original"


def test_indexing_failure_preserves_existing_index(tmp_path, monkeypatch):
    """When embedding or parsing fails during refresh, existing index is preserved and staging is cleaned up."""
    import app.config as config
    monkeypatch.setattr(config, "INDEX_DIR", str(tmp_path))

    index_name = "test_repo"
    existing_index = tmp_path / index_name
    existing_index.mkdir()
    (existing_index / "existing_marker.txt").write_text("active_index_data")

    # Mock pipeline dependencies
    events = []
    def emit(step, msg, progress, **kwargs):
        events.append((step, msg))

    monkeypatch.setattr("api.services.indexing_service._check_ollama_running", lambda: True)
    monkeypatch.setattr("api.services.indexing_service._ensure_embedding_model_available", lambda emit, model: True)

    mock_load_repo = MagicMock(return_value=str(tmp_path / "test_repo"))
    mock_filter = MagicMock(return_value=["file1.py"])
    mock_load_docs = MagicMock(return_value=[MagicMock()])
    mock_parse = MagicMock(return_value=[MagicMock()])
    mock_context = MagicMock(return_value=MagicMock())
    mock_build_vector = MagicMock(side_effect=RuntimeError("Embedding model crashed"))

    mock_splitter_instance = MagicMock()
    mock_splitter_instance.get_nodes_from_documents.return_value = []
    mock_splitter_cls = MagicMock(return_value=mock_splitter_instance)

    pipeline_deps = (
        mock_load_repo,
        mock_filter,
        mock_load_docs,
        mock_parse,
        mock_context,
        mock_build_vector,
        mock_splitter_cls,
    )
    monkeypatch.setattr("api.services.indexing_service._load_pipeline_dependencies", lambda emit: pipeline_deps)
    monkeypatch.setattr("app.indexing.incremental.run_incremental_indexing", lambda r, i: False)

    with pytest.raises(RuntimeError, match="Embedding model crashed"):
        _run_pipeline_sync("https://github.com/org/test_repo", emit)

    # Existing index MUST remain intact!
    assert existing_index.exists()
    assert (existing_index / "existing_marker.txt").read_text() == "active_index_data"

    # No staging directories should be left lying around
    staging_dirs = [d for d in tmp_path.iterdir() if "stage_" in d.name]
    assert len(staging_dirs) == 0


def test_clone_failure_preserves_existing_clone(tmp_path, monkeypatch):
    """When repo loader clone fails, candidate target is untouched."""
    from app.ingestion.repo_loader import load_repository, CloneRepositoryError
    import app.config as config
    monkeypatch.setattr(config, "REPOS_DIR", str(tmp_path))

    repo_dir = tmp_path / "failing-repo"
    repo_dir.mkdir()
    (repo_dir / "tracked_code.py").write_text("print('stable')")

    def failing_clone(src, target):
        raise RuntimeError("Network timeout during git clone")

    monkeypatch.setattr("app.ingestion.repo_loader._clone_repository", failing_clone)

    with pytest.raises(CloneRepositoryError):
        load_repository("https://github.com/org/failing-repo")

    # Original clone must still be there
    assert repo_dir.exists()
    assert (repo_dir / "tracked_code.py").read_text() == "print('stable')"


def test_concurrent_refresh_locks():
    """Verify concurrent refresh locks prevent multiple simultaneous refresh operations on the same repo."""
    repo_id = "test-repo-lock-" + uuid.uuid4().hex[:6]
    lock = _get_refresh_lock(repo_id)

    # Acquire lock in thread 1
    acquired_1 = lock.acquire(blocking=False)
    assert acquired_1 is True

    # Try acquiring in thread 2 -> must fail
    def attempt_acquire(result_list):
        l2 = _get_refresh_lock(repo_id)
        result_list.append(l2.acquire(blocking=False))

    results = []
    t = threading.Thread(target=attempt_acquire, args=(results,))
    t.start()
    t.join()

    assert results == [False]

    # Release lock
    lock.release()

    # Now acquire should succeed
    results2 = []
    t2 = threading.Thread(target=attempt_acquire, args=(results2,))
    t2.start()
    t2.join()
    assert results2 == [True]
    lock.release()


def test_interrupted_refresh_preserves_prior_index(tmp_path, monkeypatch):
    """When refresh is cancelled/interrupted midway, original index remains and staging is removed."""
    import app.config as config
    monkeypatch.setattr(config, "INDEX_DIR", str(tmp_path))

    index_name = "active_repo"
    existing_index = tmp_path / index_name
    existing_index.mkdir()
    (existing_index / "data.db").write_text("v1_data")

    events = []
    def emit(step, msg, progress, **kwargs):
        events.append((step, msg))

    monkeypatch.setattr("api.services.indexing_service._check_ollama_running", lambda: True)
    monkeypatch.setattr("api.services.indexing_service._ensure_embedding_model_available", lambda emit, model: True)

    def interrupt_during_graph(*args, **kwargs):
        raise KeyboardInterrupt("Simulated task cancellation / SIGINT")

    mock_load_repo = MagicMock(return_value=str(tmp_path / "active_repo"))
    mock_filter = MagicMock(return_value=["main.py"])
    mock_load_docs = MagicMock(return_value=[MagicMock()])
    mock_parse = MagicMock(return_value=[MagicMock()])
    mock_context = MagicMock(return_value=MagicMock())
    mock_build_vector = MagicMock()

    mock_splitter_instance = MagicMock()
    mock_splitter_instance.get_nodes_from_documents.return_value = []
    mock_splitter_cls = MagicMock(return_value=mock_splitter_instance)

    pipeline_deps = (
        mock_load_repo,
        mock_filter,
        mock_load_docs,
        mock_parse,
        mock_context,
        mock_build_vector,
        mock_splitter_cls,
    )
    monkeypatch.setattr("api.services.indexing_service._load_pipeline_dependencies", lambda emit: pipeline_deps)
    monkeypatch.setattr("app.indexing.incremental.run_incremental_indexing", lambda r, i: False)
    monkeypatch.setattr("app.indexing.incremental.build_initial_manifest", lambda *a, **k: None)
    monkeypatch.setattr("app.ingestion.git_history.build_and_save_full_git_history", lambda *a, **k: None)
    monkeypatch.setattr("app.parsing.relationship_graph.RelationshipGraphBuilder", interrupt_during_graph)

    with pytest.raises(KeyboardInterrupt):
        _run_pipeline_sync("https://github.com/org/active_repo", emit)

    # Active index remains untouched
    assert existing_index.exists()
    assert (existing_index / "data.db").read_text() == "v1_data"

    # Staging artifacts cleaned up
    stages = [p for p in tmp_path.iterdir() if "stage_" in p.name]
    assert len(stages) == 0


def test_successful_refresh_flow(tmp_path, monkeypatch):
    """Full refresh flow: stages in new dir, validates, atomically swaps, invalidates cache."""
    import app.config as config
    monkeypatch.setattr(config, "INDEX_DIR", str(tmp_path))

    index_name = "prod_repo"
    existing_index = tmp_path / index_name
    existing_index.mkdir()
    (existing_index / "manifest.json").write_text('{"v": 1}')

    events = []
    def emit(step, msg, progress, **kwargs):
        events.append((step, msg))

    monkeypatch.setattr("api.services.indexing_service._check_ollama_running", lambda: True)
    monkeypatch.setattr("api.services.indexing_service._ensure_embedding_model_available", lambda emit, model: True)

    def mock_build_vector(nodes, target_name):
        # Creates valid chroma files in target dir
        target = tmp_path / target_name
        chroma = target / "chroma"
        chroma.mkdir(parents=True, exist_ok=True)
        (chroma / "chroma.sqlite3").write_bytes(b"SQLite format 3\x00 new_vector_data")
        (target / "manifest.json").write_text('{"v": 2}')

    mock_load_repo = MagicMock(return_value=str(tmp_path / "prod_repo"))
    mock_filter = MagicMock(return_value=["app.py"])
    mock_load_docs = MagicMock(return_value=[MagicMock()])
    mock_parse = MagicMock(return_value=[MagicMock()])
    mock_context = MagicMock(return_value=MagicMock())

    mock_splitter_instance = MagicMock()
    mock_splitter_instance.get_nodes_from_documents.return_value = []
    mock_splitter_cls = MagicMock(return_value=mock_splitter_instance)

    pipeline_deps = (
        mock_load_repo,
        mock_filter,
        mock_load_docs,
        mock_parse,
        mock_context,
        mock_build_vector,
        mock_splitter_cls,
    )
    monkeypatch.setattr("api.services.indexing_service._load_pipeline_dependencies", lambda emit: pipeline_deps)
    monkeypatch.setattr("app.indexing.incremental.run_incremental_indexing", lambda r, i: False)
    monkeypatch.setattr("app.indexing.incremental.build_initial_manifest", lambda *a, **k: None)
    monkeypatch.setattr("app.ingestion.git_history.build_and_save_full_git_history", lambda *a, **k: None)

    cache_invalidated = []
    monkeypatch.setattr(
        "app.services.qa_service.invalidate_index_cache",
        lambda idx: cache_invalidated.append(idx),
    )

    result = _run_pipeline_sync("https://github.com/org/prod_repo", emit)

    assert result is not None
    assert result["index_name"] == "prod_repo"
    # Target now has v2 manifest and valid sqlite
    assert (existing_index / "manifest.json").read_text() == '{"v": 2}'
    assert (existing_index / "chroma" / "chroma.sqlite3").read_bytes() == b"SQLite format 3\x00 new_vector_data"
    assert "prod_repo" in cache_invalidated
    # Staging artifacts cleaned
    stages = [p for p in tmp_path.iterdir() if "stage_" in p.name]
    assert len(stages) == 0

