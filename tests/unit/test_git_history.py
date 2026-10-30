import os
import tempfile
import pytest
import git
from app.ingestion.git_history import load_git_history_for_file, save_git_history_dict, load_persisted_git_history
from app.config import INDEX_GIT_HISTORY


def test_git_history_extraction_and_chunking():
    # Force enabled for test
    assert INDEX_GIT_HISTORY is True
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Initialize a new git repo
        repo = git.Repo.init(tmp_dir)
        
        # Create a test file
        file_path = os.path.join(tmp_dir, "code.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("def func():\n    print('Hello World')\n")
            
        # Commit the file
        repo.index.add(["code.py"])
        repo.index.commit("Initial commit adding code.py")
        
        # Modify the file and commit again
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("def func():\n    print('Hello World!')\n# New Comment\n")
            
        repo.index.add(["code.py"])
        repo.index.commit("Update code.py comment and print statement")
        
        # Extract git history
        docs = load_git_history_for_file(file_path, tmp_dir)
        
        # Assertions
        assert len(docs) > 0
        
        # Check metadata
        for doc in docs:
            assert doc.metadata["file_name"] == "code.py"
            assert doc.metadata["path"] == "code.py"
            assert doc.metadata["doc_type"] == "git_history"
            
        # Join text and check if it contains the commit messages
        combined_text = "\n".join([doc.text for doc in docs])
        assert "Initial commit adding code.py" in combined_text
        assert "Update code.py comment" in combined_text
        assert "+# New Comment" in combined_text
        
        # Test saving and loading persisted history dict
        history_dict = {file_path: docs}
        save_git_history_dict(history_dict, "test_repo_index")
        
        loaded_docs = load_persisted_git_history("test_repo_index")
        assert len(loaded_docs) == len(docs)
        assert loaded_docs[0].metadata["file_name"] == "code.py"
