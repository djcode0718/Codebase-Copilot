import os
import pytest
from unittest.mock import patch, MagicMock

from app.services.repo_stats_service import get_repo_stats, handle_aggregation_query


def test_get_repo_stats_success(tmp_path):
    # Mock index directory
    index_name = "Mock-Repo"
    
    # Create mock codebase_context.txt
    mock_context_content = (
        "## Project File Structure\n"
        "app/main.py\n"
        "app/utils.py\n"
        "tests/test_main.py\n"
        "README.md\n"
        "## Next Section\n"
    )
    
    mock_graph_content = {
        "app.main.start": ["app.utils.helper"],
        "app.utils.helper": []
    }

    # Patch INDEX_DIR to use our temp path
    with patch("app.services.repo_stats_service.INDEX_DIR", str(tmp_path)), \
         patch("app.services.repo_stats_service._get_chroma_collection") as mock_chroma, \
         patch("os.path.exists", return_value=True):
         
        # Mock Chroma Collection
        mock_coll_obj = MagicMock()
        mock_coll_obj.count.return_value = 42
        mock_chroma.return_value = (None, mock_coll_obj)
        
        # Mock open for codebase_context.txt and relationship_graph.json
        def mock_open_fn(filepath, mode="r", encoding=None):
            m = MagicMock()
            if "codebase_context.txt" in filepath:
                m.__enter__.return_value.readlines.return_value = mock_context_content.splitlines(keepends=True)
            elif "relationship_graph.json" in filepath:
                m.__enter__.return_value.read.return_value = "{\"app.main.start\": [], \"app.utils.helper\": []}"
            return m
            
        with patch("builtins.open", side_effect=mock_open_fn):
            stats = get_repo_stats(index_name)
            
            assert stats["chunk_count"] == 42
            assert stats["symbol_count"] == 2
            assert len(stats["files"]) == 4
            assert "app/main.py" in stats["files"]
            assert "README.md" in stats["files"]


def test_handle_aggregation_query(tmp_path):
    index_name = "Mock-Repo"
    
    mock_stats = {
        "files": [
            "app/main.py",
            "app/utils.py",
            "frontend/components/Chat.tsx",
            "tests/test_main.py",
            "README.md"
        ],
        "chunk_count": 15,
        "symbol_count": 8
    }
    
    with patch("app.services.repo_stats_service.get_repo_stats", return_value=mock_stats):
        # 1. Chunk counts
        res = handle_aggregation_query("how many chunks are indexed?", index_name)
        assert "15 code chunks" in res
        
        # 2. Symbol counts
        res = handle_aggregation_query("count of symbols", index_name)
        assert "8 defined symbols" in res
        
        # 3. Specific folder counts
        res = handle_aggregation_query("how many files in app folder", index_name)
        assert "2 indexed files in the 'app'" in res
        
        # 4. Specific extension counts
        res = handle_aggregation_query("how many py files are there", index_name)
        assert "3 files with the '.py'" in res
        
        res = handle_aggregation_query("list all tsx components", index_name)
        assert "1 files with the '.tsx'" in res
        
        # 5. Default stats
        res = handle_aggregation_query("how many files in total?", index_name)
        assert "5 indexed source files" in res
        assert "15 chunks" in res
        assert "8 symbols" in res

        # 6. Test files filtering
        res = handle_aggregation_query("how many test files?", index_name)
        assert "There are 1 indexed test files in the repository." in res

        res = handle_aggregation_query("how many python test files?", index_name)
        assert "There are 1 test files with the '.py' extension in the repository." in res

        res = handle_aggregation_query("how many test files in frontend?", index_name)
        assert "There are 0 indexed test files in the 'frontend' directory/subdirectories." in res
