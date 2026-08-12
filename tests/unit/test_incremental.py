import os
import json
import tempfile
import pytest
import git
from unittest.mock import MagicMock, patch
from llama_index.core import Document
from llama_index.core.schema import TextNode
from app.indexing.incremental import run_incremental_indexing, load_manifest, get_file_hash, build_initial_manifest


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
            mock_get_chroma.return_value = (None, mock_chroma_collection)
            
            # Run incremental indexing
            result = run_incremental_indexing(tmp_repo, index_name)
            assert result is True
            
            # Verify collection.delete was called for node_a1 (deleted) and node_b1 (modified)
            # Both deleted and modified file node IDs must be deleted from Chroma
            deleted_ids = []
            for call in mock_chroma_collection.delete.call_args_list:
                deleted_ids.extend(call.kwargs.get("ids", []))
                
            assert "node_a1" in deleted_ids
            assert "node_b1" in deleted_ids
            
            # Verify insert_nodes was called with new parsed nodes
            assert mock_idx_instance.insert_nodes.call_count == 2
            
            # Verify new manifest has updated entries
            new_manifest = load_manifest(index_name)
            assert "a.py" not in new_manifest
            assert "b.py" in new_manifest
            assert "c.py" in new_manifest
