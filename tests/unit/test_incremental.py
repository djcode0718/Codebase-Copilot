import os
import json
import tempfile
import pytest
import git
from unittest.mock import MagicMock, patch
from llama_index.core import Document
from llama_index.core.schema import TextNode
from app.indexing.incremental import (
    run_incremental_indexing,
    load_manifest,
    save_manifest,
    get_file_hash,
    build_initial_manifest,
    _safely_cleanup_obsolete_staging,
    register_active_staging_build,
    unregister_active_staging_build,
    get_active_staging_builds,
)


def test_incremental_indexing_flow():
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        # Initialize small git repo
        repo = git.Repo.init(tmp_repo)

        # 1. Create two test files
        file1 = os.path.join(tmp_repo, "a.py")
        with open(file1, "w", encoding="utf-8") as f:
            f.write("def func_a():\n    pass\n")

        file2 = os.path.join(tmp_repo, "b.py")
        with open(file2, "w", encoding="utf-8") as f:
            f.write("def func_b():\n    pass\n")

        repo.index.add(["a.py", "b.py"])
        repo.index.commit("Initial commit")

        index_name = "test_inc_index"

        # Patch config values
        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            # Setup initial manifest manually or via build_initial_manifest
            nodes = [
                TextNode(text="def func_a():\n    pass\n", metadata={"path": "a.py"}, id_="node_a1"),
                TextNode(text="def func_b():\n    pass\n", metadata={"path": "b.py"}, id_="node_b1")
            ]

            build_initial_manifest(nodes, tmp_repo, index_name)

            # Check manifest loaded correctly
            manifest = load_manifest(index_name)
            assert "a.py" in manifest
            assert "b.py" in manifest
            assert manifest["a.py"]["chunk_ids"] == ["node_a1"]
            assert manifest["b.py"]["chunk_ids"] == ["node_b1"]

            # Modify b.py, delete a.py, and add c.py
            os.remove(file1)

            with open(file2, "w", encoding="utf-8") as f:
                f.write("def func_b_updated():\n    print('updated')\n")

            file3 = os.path.join(tmp_repo, "c.py")
            with open(file3, "w", encoding="utf-8") as f:
                f.write("def func_c():\n    print('hello')\n")

            repo.index.add(["b.py", "c.py"])
            if "a.py" in repo.untracked_files:
                repo.index.remove(["a.py"])
            repo.index.commit("Commit updates")

            # Setup mocks for loading vector index and chroma
            mock_idx_instance = MagicMock()
            mock_load_idx.return_value = mock_idx_instance

            mock_chroma_collection = MagicMock()
            mock_chroma_collection.get.return_value = {"ids": ["node_a1", "node_b1"]}
            mock_get_chroma.return_value = (None, mock_chroma_collection)

            # Run incremental indexing
            result = run_incremental_indexing(tmp_repo, index_name)
            assert result is True

            # Verify collection.delete was called for node_a1 (deleted) and node_b1 (modified)
            deleted_ids = []
            for call in mock_chroma_collection.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))

            assert "node_a1" in deleted_ids
            assert "node_b1" in deleted_ids

            # Verify insert_nodes was called for code files + codebase context (3 calls)
            assert mock_idx_instance.insert_nodes.call_count == 3

            # Verify new manifest has updated entries
            new_manifest = load_manifest(index_name)
            assert "a.py" not in new_manifest
            assert "b.py" in new_manifest
            assert "c.py" in new_manifest


def test_incremental_reindexes_when_active_vectors_missing():
    """Verify unchanged files with matching hash are re-indexed if chunk IDs are absent from Chroma."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "unchanged.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def stable():\n    return 42\n")
        repo.index.add(["unchanged.py"])
        repo.index.commit("Initial commit")

        index_name = "test_missing_vectors"
        file_hash = get_file_hash(fpath)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            # Manifest records expected chunk ID 'lost_chunk_1', but active Chroma does NOT have it
            save_manifest(index_name, {
                "unchanged.py": {
                    "hash": file_hash,
                    "chunk_ids": ["lost_chunk_1"]
                }
            })

            mock_idx_instance = MagicMock()
            mock_load_idx.return_value = mock_idx_instance

            mock_chroma_collection = MagicMock()
            # Active Chroma has NO vectors (lost_chunk_1 is missing!)
            mock_chroma_collection.get.side_effect = lambda **kwargs: (
                {"ids": []} if "where" not in kwargs else {"ids": ["ctx_1"]}
            )
            mock_get_chroma.return_value = (None, mock_chroma_collection)

            result = run_incremental_indexing(tmp_repo, index_name)
            assert result is True

            # Must have re-indexed unchanged.py because its vector was missing
            assert mock_idx_instance.insert_nodes.call_count >= 1

            # Manifest must now be updated with newly generated chunk IDs
            updated_manifest = load_manifest(index_name)
            assert "unchanged.py" in updated_manifest
            new_chunk_ids = updated_manifest["unchanged.py"]["chunk_ids"]
            assert new_chunk_ids != ["lost_chunk_1"]
            assert len(new_chunk_ids) > 0


def test_incremental_preserves_codebase_context():
    """Verify codebase context is generated, and repeated runs do not create duplicate context nodes."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def main():\n    pass\n")
        repo.index.add(["app.py"])
        repo.index.commit("Initial commit")

        index_name = "test_context_preservation"
        fhash = get_file_hash(fpath)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {
                "app.py": {"hash": fhash, "chunk_ids": ["app_node_1"]}
            })

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            # First run: active Chroma has app_node_1, but context is missing
            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_node_1"]} if "where" not in kwargs else {"ids": []}
            )
            mock_get_chroma.return_value = (None, mock_col)

            res1 = run_incremental_indexing(tmp_repo, index_name)
            assert res1 is True

            # Context must have been built and inserted
            inserted_nodes = []
            for call in mock_idx.insert_nodes.call_args_list:
                nodes = call.args[0] if call.args else []
                inserted_nodes.extend(nodes)

            context_nodes = [n for n in inserted_nodes if getattr(n, "metadata", {}).get("path") == "_codebase_context"]
            assert len(context_nodes) >= 1

            # Second run: active Chroma already has app_node_1 AND context node
            mock_idx.reset_mock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_node_1", "ctx_node_1"]} if "where" not in kwargs else {"ids": ["ctx_node_1"]}
            )

            res2 = run_incremental_indexing(tmp_repo, index_name)
            assert res2 is True

            # Zero re-insertions on idempotent run
            assert mock_idx.insert_nodes.call_count == 0


def test_incremental_purges_orphaned_staging_collections():
    """Verify obsolete staging collections are only purged when all safety conditions are met."""
    index_name = "test_cleanup_safety"

    # Setup mocks
    mock_client = MagicMock()
    mock_collection = MagicMock()

    # Active collection has all required manifest IDs and context
    mock_collection.get.side_effect = lambda **kwargs: (
        {"ids": ["req_1", "req_2", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
    )

    manifest = {
        "file1.py": {"hash": "h1", "chunk_ids": ["req_1"]},
        "file2.py": {"hash": "h2", "chunk_ids": ["req_2"]},
    }

    # Case A: Staging collection is obsolete and contains no unique required data
    obsolete_staging = MagicMock()
    obsolete_staging.name = f"{index_name}_stage_old999"
    obsolete_staging.get.return_value = {"ids": ["req_1", "extra_stale_1"]}

    mock_client.list_collections.return_value = [obsolete_staging]

    _safely_cleanup_obsolete_staging(index_name, mock_client, mock_collection, manifest)
    mock_client.delete_collection.assert_called_once_with(f"{index_name}_stage_old999")

    # Case B: Staging collection contains the ONLY copy of a required vector (req_3 missing in active)
    mock_client.reset_mock()
    manifest_with_missing = {
        "file1.py": {"hash": "h1", "chunk_ids": ["req_1"]},
        "file3.py": {"hash": "h3", "chunk_ids": ["req_3"]},  # not in active!
    }
    unsafe_staging = MagicMock()
    unsafe_staging.name = f"{index_name}_stage_holding_data"
    unsafe_staging.get.return_value = {"ids": ["req_3"]}

    mock_client.list_collections.return_value = [unsafe_staging]

    _safely_cleanup_obsolete_staging(index_name, mock_client, mock_collection, manifest_with_missing)
    # Must NOT delete staging collection because it holds required data
    mock_client.delete_collection.assert_not_called()


def test_repeated_incremental_refreshes_are_idempotent():
    """Verify running incremental refresh twice without changes results in stable, idempotent state."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "mod.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("x = 10\n")
        repo.index.add(["mod.py"])
        repo.index.commit("Initial")

        index_name = "test_idempotency"
        h = get_file_hash(fpath)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"mod.py": {"hash": h, "chunk_ids": ["mod_chunk_1"]}})

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["mod_chunk_1", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            # First run: active has all vectors and context
            res1 = run_incremental_indexing(tmp_repo, index_name)
            assert res1 is True
            assert mock_idx.insert_nodes.call_count == 0

            # Second run: identical state
            res2 = run_incremental_indexing(tmp_repo, index_name)
            assert res2 is True
            assert mock_idx.insert_nodes.call_count == 0

            manifest_after = load_manifest(index_name)
            assert manifest_after["mod.py"]["chunk_ids"] == ["mod_chunk_1"]


def test_partial_promotion_recovery():
    """Verify recovery restores active collection from disk files when active vectors are missing."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        readme_path = os.path.join(tmp_repo, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# Sample Readme\nProject docs\n")
        repo.index.add(["README.md"])
        repo.index.commit("Initial")

        index_name = "test_recovery"
        rh = get_file_hash(readme_path)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            # Manifest recorded chunks from a failed staging promotion
            save_manifest(index_name, {"README.md": {"hash": rh, "chunk_ids": ["staged_chunk_1"]}})

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            mock_client = MagicMock()
            staging_col = MagicMock()
            staging_col.name = f"{index_name}_stage_fail1"
            staging_col.get.return_value = {"ids": ["staged_chunk_1"]}
            mock_client.list_collections.return_value = [staging_col]

            mock_col = MagicMock()
            # Active collection is EMPTY (missing staged_chunk_1 and context)
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": []} if "where" not in kwargs else {"ids": []}
            )
            mock_get_chroma.return_value = (mock_client, mock_col)

            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True

            # Active collection was restored via insertion
            assert mock_idx.insert_nodes.call_count >= 1

            # Manifest was updated with new active chunk IDs
            recovered_manifest = load_manifest(index_name)
            assert recovered_manifest["README.md"]["chunk_ids"] != ["staged_chunk_1"]


# ─── Tests for Finding 1 (CRIT-1: In-Flight Staging Safety) ───────────────────

def test_staging_cleanup_allows_sole_in_flight_current_refresh():
    """Verify cleanup proceeds when the current refresh is the sole in-flight operation."""
    index_name = "test_cleanup_sole_refresh"
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.get.side_effect = lambda **kwargs: (
        {"ids": ["r1", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
    )
    manifest = {"f.py": {"hash": "h", "chunk_ids": ["r1"]}}

    obsolete_staging = MagicMock()
    obsolete_staging.name = f"{index_name}_stage_old"
    obsolete_staging.get.return_value = {"ids": ["r1"]}
    mock_client.list_collections.return_value = [obsolete_staging]

    with patch("api.services.indexing_service._indexing_in_flight", {"repo_123"}), \
         patch("api.services.indexing_service._indexing_sources_in_flight", {"https://github.com/user/test_repo"}):
        _safely_cleanup_obsolete_staging(
            index_name,
            mock_client,
            mock_collection,
            manifest,
            current_repo_id="repo_123",
            current_source="https://github.com/user/test_repo",
        )
        mock_client.delete_collection.assert_called_once_with(f"{index_name}_stage_old")


def test_staging_cleanup_skips_when_different_repo_indexing():
    """Verify cleanup is skipped when a different repository is indexing."""
    index_name = "test_cleanup_diff_repo"
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.get.side_effect = lambda **kwargs: (
        {"ids": ["r1", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
    )
    manifest = {"f.py": {"hash": "h", "chunk_ids": ["r1"]}}

    obsolete_staging = MagicMock()
    obsolete_staging.name = f"{index_name}_stage_old"
    obsolete_staging.get.return_value = {"ids": ["r1"]}
    mock_client.list_collections.return_value = [obsolete_staging]

    with patch("api.services.indexing_service._indexing_in_flight", {"repo_diff"}), \
         patch("api.services.indexing_service._indexing_sources_in_flight", {"https://github.com/different/repo"}):
        _safely_cleanup_obsolete_staging(
            index_name,
            mock_client,
            mock_collection,
            manifest,
            current_repo_id="repo_123",
            current_source="https://github.com/user/test_repo",
        )
        mock_client.delete_collection.assert_not_called()


def test_staging_cleanup_skips_when_concurrent_operation_same_repo_active():
    """Verify cleanup is skipped when another concurrent operation for the same repo is active."""
    index_name = "test_cleanup_concurrent_same_repo"
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.get.side_effect = lambda **kwargs: (
        {"ids": ["r1", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
    )
    manifest = {"f.py": {"hash": "h", "chunk_ids": ["r1"]}}

    obsolete_staging = MagicMock()
    obsolete_staging.name = f"{index_name}_stage_old"
    obsolete_staging.get.return_value = {"ids": ["r1"]}
    mock_client.list_collections.return_value = [obsolete_staging]

    with patch("api.services.indexing_service._indexing_in_flight", {"repo_123", "repo_123_concurrent"}), \
         patch("api.services.indexing_service._indexing_sources_in_flight", {"https://github.com/user/test_repo"}):
        _safely_cleanup_obsolete_staging(
            index_name,
            mock_client,
            mock_collection,
            manifest,
            current_repo_id="repo_123",
            current_source="https://github.com/user/test_repo",
        )
        mock_client.delete_collection.assert_not_called()


def test_staging_cleanup_skips_when_staging_build_actively_writing():
    """Verify cleanup is skipped when a candidate collection is in active staging builds."""
    index_name = "test_cleanup_active_staging"
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.get.side_effect = lambda **kwargs: (
        {"ids": ["r1", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
    )
    manifest = {"f.py": {"hash": "h", "chunk_ids": ["r1"]}}

    obsolete_staging = MagicMock()
    obsolete_staging.name = f"{index_name}_stage_writing"
    obsolete_staging.get.return_value = {"ids": ["r1"]}
    mock_client.list_collections.return_value = [obsolete_staging]

    with patch("api.services.indexing_service._indexing_in_flight", {"repo_123"}), \
         patch("api.services.indexing_service._indexing_sources_in_flight", {"https://github.com/user/test_repo"}):
        _safely_cleanup_obsolete_staging(
            index_name,
            mock_client,
            mock_collection,
            manifest,
            current_repo_id="repo_123",
            current_source="https://github.com/user/test_repo",
            active_staging_builds={f"{index_name}_stage_writing"},
        )
        mock_client.delete_collection.assert_not_called()


def test_staging_cleanup_fails_safe_when_tracking_unavailable():
    """Verify cleanup fails safe by retaining staging when in-flight tracking is unavailable."""
    index_name = "test_cleanup_fail_safe"
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.get.side_effect = lambda **kwargs: (
        {"ids": ["r1", "ctx_1"]} if "where" not in kwargs else {"ids": ["ctx_1"]}
    )
    manifest = {"f.py": {"hash": "h", "chunk_ids": ["r1"]}}

    obsolete_staging = MagicMock()
    obsolete_staging.name = f"{index_name}_stage_old"
    obsolete_staging.get.return_value = {"ids": ["r1"]}
    mock_client.list_collections.return_value = [obsolete_staging]

    with patch("api.services.indexing_service._indexing_in_flight", None):
        _safely_cleanup_obsolete_staging(
            index_name,
            mock_client,
            mock_collection,
            manifest,
            current_repo_id="repo_123",
            current_source="https://github.com/user/test_repo",
        )
        mock_client.delete_collection.assert_not_called()


# ─── Tests for Finding 2 (HIGH-1: Failure-Safe Context Replacement) ───────────

def test_context_generation_failure_preserves_old_context():
    """Verify that when context generation fails, existing context nodes in Chroma and docstore are preserved."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    pass\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_gen_fail"

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": "old_hash", "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            # Active Chroma has old context node
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_1", "ctx_old_1"]} if "where" not in kwargs else {"ids": ["ctx_old_1"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            with patch("app.indexing.context_builder.build_codebase_context", side_effect=RuntimeError("Context build crash")):
                res = run_incremental_indexing(tmp_repo, index_name)
                assert res is True

                # Old context node ctx_old_1 must NOT have been deleted
                deleted_ids = []
                for call in mock_col.delete.call_args_list:
                    deleted_ids.extend(call.kwargs.get("ids", []))
                assert "ctx_old_1" not in deleted_ids


def test_context_insertion_failure_preserves_old_context():
    """Verify that when context insertion fails, old context is preserved and partial nodes rolled back."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    pass\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_insert_fail"

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": "old_hash", "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            # First insert (code file) succeeds, second insert (context nodes) raises
            mock_idx.insert_nodes.side_effect = [None, RuntimeError("Chroma write timeout")]
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_1", "ctx_old_1"]} if "where" not in kwargs else {"ids": ["ctx_old_1"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True

            # Old context node ctx_old_1 must NOT have been deleted
            deleted_ids = []
            for call in mock_col.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))
            assert "ctx_old_1" not in deleted_ids


def test_successful_context_replacement_removes_old_nodes_from_chroma_and_docstore():
    """Verify replacement context cleanly deletes obsolete context nodes from both Chroma and docstore."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    pass\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_replacement"

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": "old_hash", "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_idx.docstore = MagicMock()
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_1", "ctx_old_99"]} if "where" not in kwargs else {"ids": ["ctx_old_99"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True

            # Old context ctx_old_99 must be deleted from Chroma
            deleted_chroma_ids = []
            for call in mock_col.delete.call_args_list:
                deleted_chroma_ids.extend(call.kwargs.get("ids", []))
            assert "ctx_old_99" in deleted_chroma_ids

            # Old context ctx_old_99 must be deleted from docstore
            mock_idx.docstore.delete_document.assert_any_call("ctx_old_99", raise_error=False)


def test_repeated_refreshes_do_not_accumulate_duplicate_context():
    """Verify repeated refreshes do not accumulate duplicate context nodes across runs."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    pass\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_no_duplicates"
        fhash = get_file_hash(fpath)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": fhash, "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            # Run 1: Active has app_1 and context node ctx_v1
            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_1", "ctx_v1"]} if "where" not in kwargs else {"ids": ["ctx_v1"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            # Idempotent run: zero insertions
            res1 = run_incremental_indexing(tmp_repo, index_name)
            assert res1 is True
            assert mock_idx.insert_nodes.call_count == 0

            # Run 2: File modified -> triggers context replacement
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("def run():\n    return 100\n")
            repo.index.add(["app.py"])
            repo.index.commit("Update")

            res2 = run_incremental_indexing(tmp_repo, index_name)
            assert res2 is True

            # Obsolete context node ctx_v1 must have been deleted
            deleted_ids = []
            for call in mock_col.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))
            assert "ctx_v1" in deleted_ids


def test_partial_context_failure_recoverable_on_next_refresh():
    """Verify that if obsolete context deletion fails once, the next refresh cleans it up."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    pass\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_recovery_next_run"

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": "old_hash", "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            # Active Chroma has lingering previous nodes from a partial deletion failure
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["app_1", "ctx_stale_1", "ctx_stale_2"]} if "where" not in kwargs else {"ids": ["ctx_stale_1", "ctx_stale_2"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True

            # Both stale context nodes must have been targeted for deletion
            deleted_ids = []
            for call in mock_col.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))
            assert "ctx_stale_1" in deleted_ids
            assert "ctx_stale_2" in deleted_ids


# ─────────────────────────────────────────────────────────────────────────────
# Fix 1: Context reconciliation on unchanged refresh
# ─────────────────────────────────────────────────────────────────────────────

def test_context_reconciliation_on_unchanged_refresh_after_failed_deletion():
    """
    Reproduce exact sequence:
    1. Existing context present (gen1).
    2. Files changed, new context inserted (gen2), but old-context deletion failed.
    3. Chroma retains both gen1 and gen2 context nodes.
    4. Next refresh runs with UNCHANGED files.
    5. Next refresh detects multiple generations, reconciles, and deletes old context nodes.
    6. Further unchanged refresh leaves single generation and zero insertions.
    """
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    return 42\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_reconcile_unchanged"
        fhash = get_file_hash(fpath)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": fhash, "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_docstore = MagicMock()
            mock_docstore.get_document.return_value = MagicMock()
            mock_idx.docstore = mock_docstore
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()

            # Active Chroma has both gen1 (stale) and gen2 nodes due to prior deletion failure
            ctx_records_initial = {
                "ids": ["ctx_gen1_0", "ctx_gen2_0"],
                "metadatas": [
                    {
                        "path": "_codebase_context",
                        "context_generation": "ctx_gen_1111_aaaa",
                        "context_chunk_index": 0,
                        "context_total_chunks": 1,
                    },
                    {
                        "path": "_codebase_context",
                        "context_generation": "ctx_gen_2222_bbbb",
                        "context_chunk_index": 0,
                        "context_total_chunks": 1,
                    },
                ],
            }

            def col_get(**kwargs):
                if kwargs.get("where") == {"path": "_codebase_context"}:
                    return ctx_records_initial
                return {"ids": ["app_1", "ctx_gen1_0", "ctx_gen2_0"]}

            mock_col.get.side_effect = col_get
            mock_get_chroma.return_value = (None, mock_col)

            # Step 4: Refresh runs with UNCHANGED files
            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True

            # Step 5: Verification that old context was deleted and new replacement was inserted
            assert mock_idx.insert_nodes.call_count == 1
            deleted_ids = []
            for call in mock_col.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))
            assert "ctx_gen1_0" in deleted_ids
            assert "ctx_gen2_0" in deleted_ids

            # Step 6: Next unchanged refresh has exactly 1 generation and docstore present
            mock_idx.reset_mock()
            mock_col.reset_mock()

            ctx_records_clean = {
                "ids": ["ctx_gen3_0"],
                "metadatas": [
                    {
                        "path": "_codebase_context",
                        "context_generation": "ctx_gen_3333_cccc",
                        "context_chunk_index": 0,
                        "context_total_chunks": 1,
                    }
                ],
            }

            mock_col.get.side_effect = lambda **kwargs: (
                ctx_records_clean if kwargs.get("where") == {"path": "_codebase_context"}
                else {"ids": ["app_1", "ctx_gen3_0"]}
            )

            res2 = run_incremental_indexing(tmp_repo, index_name)
            assert res2 is True
            # Should early return with 0 insertions and 0 deletions
            assert mock_idx.insert_nodes.call_count == 0
            assert mock_col.delete.call_count == 0


def test_context_chroma_docstore_mismatch_triggers_reconciliation():
    """If Chroma has a context node that docstore is missing, unchanged refresh reconciles."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    return 42\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_docstore_mismatch"
        fhash = get_file_hash(fpath)

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": fhash, "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_docstore = MagicMock()
            # Node exists in Chroma but docstore returns None!
            mock_docstore.get_document.return_value = None
            mock_idx.docstore = mock_docstore
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {
                    "ids": ["ctx_orphan"],
                    "metadatas": [{
                        "path": "_codebase_context",
                        "context_generation": "ctx_gen_test",
                        "context_chunk_index": 0,
                        "context_total_chunks": 1,
                    }]
                } if kwargs.get("where") == {"path": "_codebase_context"}
                else {"ids": ["app_1", "ctx_orphan"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True
            # Should have reconciled and inserted new context
            assert mock_idx.insert_nodes.call_count == 1
            deleted_ids = []
            for call in mock_col.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))
            assert "ctx_orphan" in deleted_ids


def test_context_deletion_chroma_failure_does_not_crash_refresh():
    """If collection.delete fails during context cleanup, the refresh does not crash."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    return 42\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_chroma_delete_fail"

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": "old_hash", "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["ctx_old"], "metadatas": [{"path": "_codebase_context"}]}
                if kwargs.get("where") == {"path": "_codebase_context"}
                else {"ids": ["app_1", "ctx_old"]}
            )
            mock_col.delete.side_effect = RuntimeError("Chroma connection dropped during delete")
            mock_get_chroma.return_value = (None, mock_col)

            # Does not raise RuntimeError; logs warning and finishes safely
            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True
            # New context was inserted before delete attempted
            assert mock_idx.insert_nodes.call_count >= 1


def test_context_docstore_deletion_failure_handled_safely():
    """If docstore document deletion throws, refresh completes without error."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "app.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def run():\n    return 42\n")
        repo.index.add(["app.py"])
        repo.index.commit("Init")

        index_name = "test_ctx_docstore_delete_fail"

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir), \
             patch("app.indexing.incremental.load_vector_index") as mock_load_idx, \
             patch("app.indexing.incremental._get_chroma_collection") as mock_get_chroma:

            save_manifest(index_name, {"app.py": {"hash": "old_hash", "chunk_ids": ["app_1"]}})

            mock_idx = MagicMock()
            mock_docstore = MagicMock()
            mock_docstore.delete_document.side_effect = Exception("Docstore SQLite lock")
            mock_idx.docstore = mock_docstore
            mock_load_idx.return_value = mock_idx

            mock_col = MagicMock()
            mock_col.get.side_effect = lambda **kwargs: (
                {"ids": ["ctx_old"], "metadatas": [{"path": "_codebase_context"}]}
                if kwargs.get("where") == {"path": "_codebase_context"}
                else {"ids": ["app_1", "ctx_old"]}
            )
            mock_get_chroma.return_value = (None, mock_col)

            res = run_incremental_indexing(tmp_repo, index_name)
            assert res is True


# ─────────────────────────────────────────────────────────────────────────────
# Fix 2 & Fix 3: Staging lifecycle registration and mtime heuristic removal
# ─────────────────────────────────────────────────────────────────────────────

def test_staging_build_lifecycle_registered_and_unregistered():
    """Verify that an active staging build registers immediately and unregisters in finally."""
    from api.services.indexing_service import _run_pipeline_sync

    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "main.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def main():\n    print('hello')\n")
        repo.index.add(["main.py"])
        repo.index.commit("Init")

        index_name = os.path.basename(os.path.normpath(tmp_repo))
        # Create existing index dir so is_existing is True and staging is used
        os.makedirs(os.path.join(tmp_index_dir, index_name), exist_ok=True)

        registered_during_build = []

        def mock_build_vector_index(nodes, b_idx_name):
            # Check registry during build execution
            active_builds = get_active_staging_builds()
            registered_during_build.extend(list(active_builds))

        mock_deps = (
            lambda src: tmp_repo,                          # load_repository
            lambda rp: [fpath],                            # filter_files
            lambda files, rp: [Document(text="code")],     # load_documents
            lambda docs: [TextNode(text="code", id_="n1")],# parse_documents
            lambda vf, rp, iname: Document(text="context"),# build_codebase_context
            mock_build_vector_index,                       # build_vector_index
            MagicMock(get_nodes_from_documents=lambda docs: [TextNode(text="ctx", id_="c1")]), # SentenceSplitter
        )

        with patch("app.config.INDEX_DIR", tmp_index_dir), \
             patch("api.services.indexing_service._validate_staged_index"), \
             patch("api.services.indexing_service._promote_staged_index"), \
             patch("api.services.indexing_service._check_ollama_running", return_value=True), \
             patch("api.services.indexing_service._ensure_embedding_model_available", return_value=True), \
             patch("api.services.indexing_service._load_pipeline_dependencies", return_value=mock_deps), \
             patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir):

            emit = MagicMock()
            res = _run_pipeline_sync(
                source=tmp_repo,
                emit=emit,
            )

            # Build was registered during embedding
            assert len(registered_during_build) >= 1
            stg_name = registered_during_build[0]
            assert stg_name.startswith(f"{index_name}_stage_")

            # After pipeline finishes, registration must be removed in finally
            assert stg_name not in get_active_staging_builds()


def test_staging_build_unregistered_on_pipeline_failure():
    """Verify that an active staging build is unregistered even if pipeline fails."""
    from api.services.indexing_service import _run_pipeline_sync

    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        fpath = os.path.join(tmp_repo, "main.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("def main():\n    pass\n")
        repo.index.add(["main.py"])
        repo.index.commit("Init")

        index_name = os.path.basename(os.path.normpath(tmp_repo))
        os.makedirs(os.path.join(tmp_index_dir, index_name), exist_ok=True)

        registered_during_build = []

        def failing_build_vector_index(nodes, b_idx_name):
            active_builds = get_active_staging_builds()
            registered_during_build.extend(list(active_builds))
            raise RuntimeError("Ollama embedding engine crashed")

        mock_deps = (
            lambda src: tmp_repo,
            lambda rp: [fpath],
            lambda files, rp: [Document(text="code")],
            lambda docs: [TextNode(text="code", id_="n1")],
            lambda vf, rp, iname: Document(text="context"),
            failing_build_vector_index,
            MagicMock(get_nodes_from_documents=lambda docs: [TextNode(text="ctx", id_="c1")]),
        )

        with patch("app.config.INDEX_DIR", tmp_index_dir), \
             patch("api.services.indexing_service._check_ollama_running", return_value=True), \
             patch("api.services.indexing_service._ensure_embedding_model_available", return_value=True), \
             patch("api.services.indexing_service._load_pipeline_dependencies", return_value=mock_deps), \
             patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir):

            emit = MagicMock()
            with pytest.raises(RuntimeError, match="Ollama embedding engine crashed"):
                _run_pipeline_sync(
                    source=tmp_repo,
                    emit=emit,
                )

            assert len(registered_during_build) >= 1
            stg_name = registered_during_build[0]
            # Must be unregistered in finally
            assert stg_name not in get_active_staging_builds()


def test_concurrent_builds_do_not_unregister_each_other():
    """Concurrent staging builds do not interfere with each other's registration."""
    register_active_staging_build("repo_stage_aaa111")
    register_active_staging_build("repo_stage_bbb222")

    current = get_active_staging_builds()
    assert "repo_stage_aaa111" in current
    assert "repo_stage_bbb222" in current

    unregister_active_staging_build("repo_stage_aaa111")

    after = get_active_staging_builds()
    assert "repo_stage_aaa111" not in after
    assert "repo_stage_bbb222" in after

    unregister_active_staging_build("repo_stage_bbb222")
    assert "repo_stage_bbb222" not in get_active_staging_builds()


def test_active_build_protected_even_when_mtime_older_than_15_seconds():
    """An active build registered in the registry is NEVER deleted even if mtime > 15s."""
    with tempfile.TemporaryDirectory() as tmp_index_dir:
        index_name = "test_repo"
        stg_name = f"{index_name}_stage_active99"

        # Create staging dir and make mtime 60s old (> 15s)
        stg_dir = os.path.join(tmp_index_dir, stg_name)
        os.makedirs(stg_dir, exist_ok=True)
        old_time = os.path.getmtime(stg_dir) - 60.0
        os.utime(stg_dir, (old_time, old_time))

        # Register it in active staging builds
        register_active_staging_build(stg_name)

        mock_client = MagicMock()
        mock_stg_col = MagicMock()
        mock_stg_col.name = stg_name
        mock_client.list_collections.return_value = [mock_stg_col]

        mock_col = MagicMock()
        mock_col.get.return_value = {"ids": ["chunk_1", "ctx_1"]}

        manifest = {"a.py": {"chunk_ids": ["chunk_1"]}}

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir):
            try:
                _safely_cleanup_obsolete_staging(
                    index_name=index_name,
                    client=mock_client,
                    collection=mock_col,
                    manifest=manifest,
                )
                # Protected: client.delete_collection was NEVER called for stg_name
                for call in mock_client.delete_collection.call_args_list:
                    assert call.args[0] != stg_name
                assert os.path.exists(stg_dir)
            finally:
                unregister_active_staging_build(stg_name)


def test_obsolete_staging_cleaned_when_unregistered_and_safe():
    """Obsolete staging collections older than 300s with all safety gates passing are purged."""
    with tempfile.TemporaryDirectory() as tmp_index_dir:
        index_name = "test_repo"
        stg_name = f"{index_name}_stage_dead00"

        stg_dir = os.path.join(tmp_index_dir, stg_name)
        os.makedirs(stg_dir, exist_ok=True)
        old_time = os.path.getmtime(stg_dir) - 400.0  # > 300s fallback window
        os.utime(stg_dir, (old_time, old_time))

        mock_client = MagicMock()
        mock_stg_col = MagicMock()
        mock_stg_col.name = stg_name
        mock_stg_col.get.return_value = {"ids": ["chunk_1"]}
        mock_client.list_collections.return_value = [mock_stg_col]

        mock_col = MagicMock()
        mock_col.get.side_effect = lambda **kwargs: (
            {"ids": ["ctx_1"]} if kwargs.get("where") == {"path": "_codebase_context"}
            else {"ids": ["chunk_1", "ctx_1"]}
        )

        manifest = {"a.py": {"chunk_ids": ["chunk_1"]}}

        with patch("app.indexing.incremental.INDEX_DIR", tmp_index_dir):
            _safely_cleanup_obsolete_staging(
                index_name=index_name,
                client=mock_client,
                collection=mock_col,
                manifest=manifest,
            )
            mock_client.delete_collection.assert_called_once_with(stg_name)
            assert not os.path.exists(stg_dir)


# ─────────────────────────────────────────────────────────────────────────────
# Fix 4: Repository identity resolution
# ─────────────────────────────────────────────────────────────────────────────

def test_github_https_url_normalization():
    """GitHub HTTPS URL variations normalize to the same source in staging cleanup."""
    mock_client = MagicMock()
    mock_stg_col = MagicMock()
    mock_stg_col.name = "myrepo_stage_111"
    mock_client.list_collections.return_value = [mock_stg_col]

    mock_col = MagicMock()
    mock_col.get.side_effect = lambda **kwargs: (
        {"ids": ["ctx_1"]} if kwargs.get("where") == {"path": "_codebase_context"}
        else {"ids": ["ch1", "ctx_1"]}
    )

    manifest = {"f.py": {"chunk_ids": ["ch1"]}}

    # In-flight has https://github.com/myorg/myrepo.git
    with patch("api.services.indexing_service._indexing_in_flight", {"repo-uuid"}), \
         patch("api.services.indexing_service._indexing_sources_in_flight", {"https://github.com/myorg/myrepo.git"}):

        # Current refresh passes https://github.com/myorg/myrepo/ (no .git, trailing slash)
        _safely_cleanup_obsolete_staging(
            index_name="myrepo",
            client=mock_client,
            collection=mock_col,
            manifest=manifest,
            current_repo_id="repo-uuid",
            current_source="https://github.com/myorg/myrepo/",
        )
        # Did not abort due to mismatched source
        mock_client.delete_collection.assert_called_once_with("myrepo_stage_111")


def test_local_repository_with_origin_remote_identifies_as_local():
    """A local repo with an origin remote is matched by local filesystem path, not remote URL."""
    with tempfile.TemporaryDirectory() as tmp_repo, \
         tempfile.TemporaryDirectory() as tmp_index_dir:

        repo = git.Repo.init(tmp_repo)
        repo.create_remote("origin", "https://github.com/someuser/somerepo.git")

        mock_client = MagicMock()
        mock_stg_col = MagicMock()
        mock_stg_col.name = "somerepo_stage_222"
        mock_client.list_collections.return_value = [mock_stg_col]

        mock_col = MagicMock()
        mock_col.get.side_effect = lambda **kwargs: (
            {"ids": ["ctx_1"]} if kwargs.get("where") == {"path": "_codebase_context"}
            else {"ids": ["c1", "ctx_1"]}
        )

        manifest = {"f.py": {"chunk_ids": ["c1"]}}

        # In-flight tracking records local path: os.path.abspath(tmp_repo)
        local_src = os.path.realpath(os.path.abspath(tmp_repo)).lower()

        with patch("api.services.indexing_service._indexing_in_flight", {"local-repo-id"}), \
             patch("api.services.indexing_service._indexing_sources_in_flight", {local_src}):

            _safely_cleanup_obsolete_staging(
                index_name="somerepo",
                client=mock_client,
                collection=mock_col,
                manifest=manifest,
                repo_path=tmp_repo,
                current_repo_id="local-repo-id",
            )
            # Matched local_candidate to in_flight_sources and safely purged staging
            mock_client.delete_collection.assert_called_once_with("somerepo_stage_222")


def test_local_repository_without_remote_matches_local_source():
    """A local repository with no git remotes matches local filesystem source path."""
    with tempfile.TemporaryDirectory() as tmp_repo:
        repo = git.Repo.init(tmp_repo)
        assert len(repo.remotes) == 0

        mock_client = MagicMock()
        mock_stg_col = MagicMock()
        mock_stg_col.name = "localrepo_stage_333"
        mock_client.list_collections.return_value = [mock_stg_col]

        mock_col = MagicMock()
        mock_col.get.side_effect = lambda **kwargs: (
            {"ids": ["ctx_1"]} if kwargs.get("where") == {"path": "_codebase_context"}
            else {"ids": ["c1", "ctx_1"]}
        )

        manifest = {"f.py": {"chunk_ids": ["c1"]}}
        local_src = os.path.realpath(os.path.abspath(tmp_repo)).lower()

        with patch("api.services.indexing_service._indexing_in_flight", {"local-id"}), \
             patch("api.services.indexing_service._indexing_sources_in_flight", {local_src}):

            _safely_cleanup_obsolete_staging(
                index_name="localrepo",
                client=mock_client,
                collection=mock_col,
                manifest=manifest,
                repo_path=tmp_repo,
                current_repo_id="local-id",
            )
            mock_client.delete_collection.assert_called_once_with("localrepo_stage_333")


def test_ambiguous_identity_fails_safe():
    """When tracking is active but identity is ambiguous / unresolvable, cleanup aborts."""
    mock_client = MagicMock()
    mock_stg_col = MagicMock()
    mock_stg_col.name = "repo_stage_ambiguous"
    mock_client.list_collections.return_value = [mock_stg_col]

    mock_col = MagicMock()
    mock_col.get.return_value = {"ids": ["ctx_1", "c1"]}
    manifest = {"f.py": {"chunk_ids": ["c1"]}}

    # Active tracking sets exist
    with patch("api.services.indexing_service._indexing_in_flight", {"some-active-repo"}), \
         patch("api.services.indexing_service._indexing_sources_in_flight", {"https://github.com/active/repo"}):

        # Neither current_repo_id nor current_source provided, and repo_path is None
        _safely_cleanup_obsolete_staging(
            index_name="repo",
            client=mock_client,
            collection=mock_col,
            manifest=manifest,
            current_repo_id=None,
            current_source=None,
            repo_path=None,
        )
        # Must fail safe: NO deletions
        assert mock_client.delete_collection.call_count == 0
