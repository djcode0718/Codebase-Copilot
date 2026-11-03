"""
tests/unit/test_staged_index_promotion.py
──────────────────────────────────────────
Unit tests for safe Chroma staged-index promotion and atomic rollback.
"""

import os
import shutil
import tempfile
import pytest
import chromadb

import app.config
import api.services.indexing_service
from api.services.indexing_service import _promote_staged_index


def _create_chroma_collection(dir_path: str, collection_name: str, doc_ids: list):
    """Helper to create an isolated Chroma collection with explicit dummy embeddings."""
    chroma_path = os.path.join(dir_path, "chroma")
    os.makedirs(chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)
    # Using explicit dummy embeddings to skip ONNX model downloading
    col = client.get_or_create_collection(name=collection_name)
    if doc_ids:
        dummy_embeddings = [[0.1, 0.2, 0.3, 0.4] for _ in doc_ids]
        col.add(
            ids=doc_ids,
            documents=[f"Doc content for {i}" for i in doc_ids],
            embeddings=dummy_embeddings,
        )
    client.close()


def test_successful_promotion_preserves_vectors(monkeypatch):
    """Verify promotion renames staged collection, preserves vectors, and removes staging folder."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(app.config, "INDEX_DIR", td)

        staging_name = "test_repo__staging_12345"
        final_name = "test_repo"

        staging_dir = os.path.join(td, staging_name)
        final_dir = os.path.join(td, final_name)

        # Existing active index with 2 docs
        _create_chroma_collection(final_dir, final_name, ["old_1", "old_2"])

        # Staged replacement with 3 docs
        _create_chroma_collection(staging_dir, staging_name, ["new_1", "new_2", "new_3"])

        # Execute promotion
        _promote_staged_index(staging_name, final_name)

        # 1. Staging directory must no longer exist
        assert not os.path.exists(staging_dir)

        # 2. Backup directory must be cleaned up
        assert not os.path.exists(f"{final_dir}__backup_for_rollback")

        # 3. Final directory must exist and contain exactly the 3 promoted vectors under final_name
        assert os.path.exists(final_dir)
        client = chromadb.PersistentClient(path=os.path.join(final_dir, "chroma"))
        col = client.get_collection(name=final_name)
        assert col.count() == 3
        data = col.get()
        assert set(data["ids"]) == {"new_1", "new_2", "new_3"}
        client.close()


def test_collection_name_conflict_in_staging(monkeypatch):
    """Verify promotion handles duplicate final_name in staging without raising conflict errors."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(app.config, "INDEX_DIR", td)

        staging_name = "conflict_repo__staging_999"
        final_name = "conflict_repo"

        staging_dir = os.path.join(td, staging_name)
        final_dir = os.path.join(td, final_name)

        # Staging directory accidentally contains BOTH staging_name and final_name
        chroma_path = os.path.join(staging_dir, "chroma")
        os.makedirs(chroma_path, exist_ok=True)
        client = chromadb.PersistentClient(path=chroma_path)
        col_staged = client.create_collection(name=staging_name)
        col_staged.add(ids=["valid_doc"], documents=["Valid"], embeddings=[[0.1, 0.2, 0.3, 0.4]])
        # Conflicting stale collection
        col_conflict = client.create_collection(name=final_name)
        col_conflict.add(ids=["stale_doc"], documents=["Stale"], embeddings=[[0.1, 0.2, 0.3, 0.4]])
        client.close()

        # Promotion should cleanly delete the conflicting duplicate and promote staged collection
        _promote_staged_index(staging_name, final_name)

        assert os.path.exists(final_dir)
        client = chromadb.PersistentClient(path=os.path.join(final_dir, "chroma"))
        col = client.get_collection(name=final_name)
        assert col.count() == 1
        assert col.get()["ids"] == ["valid_doc"]
        client.close()


def test_rollback_restores_previous_index_on_failure(monkeypatch):
    """Verify rollback restores previous active index when staging replacement fails verification."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(app.config, "INDEX_DIR", td)

        staging_name = "fail_repo__staging_111"
        final_name = "fail_repo"

        staging_dir = os.path.join(td, staging_name)
        final_dir = os.path.join(td, final_name)

        # Existing active index with 2 original docs
        _create_chroma_collection(final_dir, final_name, ["orig_1", "orig_2"])

        # Staged index with a collection that fails post-promotion validation
        _create_chroma_collection(staging_dir, "unexpected_collection", ["staged_1"])

        with pytest.raises(ValueError, match="Promoted index validation failed"):
            _promote_staged_index(staging_name, final_name)

        # Active index must still exist and be intact with original 2 docs
        assert os.path.exists(final_dir)
        client = chromadb.PersistentClient(path=os.path.join(final_dir, "chroma"))
        col = client.get_collection(name=final_name)
        assert col.count() == 2
        assert set(col.get()["ids"]) == {"orig_1", "orig_2"}
        client.close()


def test_filesystem_replacement_failure_triggers_rollback(monkeypatch):
    """Verify rollback restores backup if moving staging_dir over final_dir fails."""
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(app.config, "INDEX_DIR", td)

        staging_name = "fs_fail__staging_222"
        final_name = "fs_fail"

        staging_dir = os.path.join(td, staging_name)
        final_dir = os.path.join(td, final_name)

        _create_chroma_collection(final_dir, final_name, ["saved_1", "saved_2"])
        _create_chroma_collection(staging_dir, staging_name, ["staged_1"])

        real_replace = os.replace

        def mock_replace(src, dst):
            # Allow moving final_dir to backup_dir, but fail when moving staging_dir to final_dir
            if src == staging_dir and dst == final_dir:
                raise OSError("Simulated disk error during replacement")
            return real_replace(src, dst)

        monkeypatch.setattr(os, "replace", mock_replace)

        with pytest.raises(OSError, match="Simulated disk error during replacement"):
            _promote_staged_index(staging_name, final_name)

        # Final dir must be restored
        assert os.path.exists(final_dir)
        client = chromadb.PersistentClient(path=os.path.join(final_dir, "chroma"))
        col = client.get_collection(name=final_name)
        assert col.count() == 2
        assert set(col.get()["ids"]) == {"saved_1", "saved_2"}
        client.close()
