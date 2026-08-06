"""
tests/test_app_file_filter.py
Unit tests for app/ingestion/file_filter.py â†’ filter_files()

Tests the core logic:
  - Accepted vs rejected file extensions
  - Ignored directories (node_modules, .git, __pycache__, etc.)
  - Nested directory traversal
  - Empty directories

Uses tmp_path â€” zero disk-state side effects.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from app.ingestion.file_filter import filter_files, VALID_EXTENSIONS, IGNORE_DIRS


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def make_file(base, rel_path: str, content: str = "# content"):
    """Create a file relative to base (creating parent dirs as needed)."""
    full = base / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return str(full)


# â”€â”€ Extension filtering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestValidExtensions:
    """Verify all accepted extensions are accepted and others rejected."""

    @pytest.mark.parametrize("ext", [
        ".py", ".js", ".ts", ".java", ".cpp", ".c", ".h", ".hpp",
        ".cs", ".go", ".rs", ".rb", ".php", ".html", ".css", ".md", ".sh",
    ])
    def test_valid_extension_accepted(self, tmp_path, ext):
        make_file(tmp_path, f"sample{ext}")
        result = filter_files(str(tmp_path))
        assert any(f.endswith(ext) for f in result), f"Expected {ext} to be accepted"

    @pytest.mark.parametrize("ext", [
        ".txt", ".log", ".yaml", ".yml", ".json", ".xml",
        ".png", ".jpg", ".gif", ".svg", ".ico",
        ".pdf", ".docx", ".xlsx",
        ".lock", ".env", ".toml", ".cfg", ".ini",
        ".pyc", ".pyo", ".so", ".dll", ".exe",
        ".zip", ".tar", ".gz",
    ])
    def test_invalid_extension_rejected(self, tmp_path, ext):
        make_file(tmp_path, f"sample{ext}")
        result = filter_files(str(tmp_path))
        assert not any(f.endswith(ext) for f in result), f"Expected {ext} to be rejected"

    def test_uppercase_extension_accepted(self, tmp_path):
        make_file(tmp_path, "SCRIPT.PY")
        result = filter_files(str(tmp_path))
        assert len(result) == 1

    def test_mixed_case_extension_accepted(self, tmp_path):
        make_file(tmp_path, "Component.JS")
        result = filter_files(str(tmp_path))
        assert len(result) == 1

    def test_no_extension_rejected(self, tmp_path):
        make_file(tmp_path, "Makefile")
        result = filter_files(str(tmp_path))
        assert result == []

    def test_dotfile_rejected(self, tmp_path):
        make_file(tmp_path, ".gitignore")
        result = filter_files(str(tmp_path))
        assert result == []


# â”€â”€ Directory filtering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestIgnoredDirectories:
    """Files inside ignored dirs should never appear in the result."""

    @pytest.mark.parametrize("ignored_dir", [
        "node_modules", ".git", ".github", "dist", "build",
        "__pycache__", "venv", "env", ".idea", ".vscode", "out", "target",
    ])
    def test_ignored_dir_files_excluded(self, tmp_path, ignored_dir):
        make_file(tmp_path, f"{ignored_dir}/should_be_ignored.py")
        result = filter_files(str(tmp_path))
        assert result == [], f"Files in '{ignored_dir}' should be excluded"

    def test_non_ignored_dir_included(self, tmp_path):
        make_file(tmp_path, "src/main.py")
        result = filter_files(str(tmp_path))
        assert len(result) == 1
        assert "main.py" in result[0]

    def test_nested_ignored_dir_excluded(self, tmp_path):
        make_file(tmp_path, "src/utils/node_modules/lib.js")
        make_file(tmp_path, "src/utils/helper.py")  # this should be included
        result = filter_files(str(tmp_path))
        assert len(result) == 1
        assert "helper.py" in result[0]

    def test_file_named_like_ignored_dir_is_accepted(self, tmp_path):
        """A FILE named 'venv' (no extension) should just be rejected by extension, not by name."""
        make_file(tmp_path, "venv.py")  # valid extension, not in an ignored dir
        result = filter_files(str(tmp_path))
        assert len(result) == 1


# â”€â”€ Traversal behaviour â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestTraversal:
    def test_empty_directory_returns_empty(self, tmp_path):
        result = filter_files(str(tmp_path))
        assert result == []

    def test_single_valid_file(self, tmp_path):
        make_file(tmp_path, "main.py")
        result = filter_files(str(tmp_path))
        assert len(result) == 1
        assert result[0].endswith("main.py")

    def test_multiple_valid_files(self, tmp_path):
        make_file(tmp_path, "a.py")
        make_file(tmp_path, "b.js")
        make_file(tmp_path, "c.ts")
        result = filter_files(str(tmp_path))
        assert len(result) == 3

    def test_deeply_nested_valid_files(self, tmp_path):
        make_file(tmp_path, "a/b/c/d/deep.py")
        result = filter_files(str(tmp_path))
        assert len(result) == 1
        assert "deep.py" in result[0]

    def test_mixed_valid_and_invalid_files(self, tmp_path):
        make_file(tmp_path, "app.py")
        make_file(tmp_path, "README.md")
        make_file(tmp_path, "config.json")  # rejected
        make_file(tmp_path, "style.css")
        make_file(tmp_path, "image.png")    # rejected
        result = filter_files(str(tmp_path))
        assert len(result) == 3
        exts = {os.path.splitext(f)[1].lower() for f in result}
        assert ".json" not in exts
        assert ".png" not in exts

    def test_returns_absolute_paths(self, tmp_path):
        make_file(tmp_path, "main.py")
        result = filter_files(str(tmp_path))
        assert all(os.path.isabs(f) for f in result)

    def test_realistic_project_structure(self, tmp_path):
        """Simulate a small Python project layout."""
        make_file(tmp_path, "src/main.py")
        make_file(tmp_path, "src/utils.py")
        make_file(tmp_path, "tests/test_main.py")
        make_file(tmp_path, "README.md")
        make_file(tmp_path, "requirements.txt")         # rejected
        make_file(tmp_path, ".gitignore")               # rejected
        make_file(tmp_path, "__pycache__/cache.pyc")    # ignored dir
        make_file(tmp_path, "venv/lib/python3.10/site.py")  # ignored dir
        make_file(tmp_path, "node_modules/dep/index.js")    # ignored dir

        result = filter_files(str(tmp_path))
        assert len(result) == 4  # main.py, utils.py, test_main.py, README.md

    def test_count_matches_len_of_result(self, tmp_path):
        for i in range(10):
            make_file(tmp_path, f"file_{i}.py")
        result = filter_files(str(tmp_path))
        assert len(result) == 10


# â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestConstants:
    def test_valid_extensions_is_a_set(self):
        assert isinstance(VALID_EXTENSIONS, set)

    def test_ignore_dirs_is_a_set(self):
        assert isinstance(IGNORE_DIRS, set)

    def test_valid_extensions_non_empty(self):
        assert len(VALID_EXTENSIONS) > 0

    def test_ignore_dirs_non_empty(self):
        assert len(IGNORE_DIRS) > 0

    def test_node_modules_in_ignore_dirs(self):
        assert "node_modules" in IGNORE_DIRS

    def test_git_in_ignore_dirs(self):
        assert ".git" in IGNORE_DIRS

    def test_pycache_in_ignore_dirs(self):
        assert "__pycache__" in IGNORE_DIRS

    def test_py_in_valid_extensions(self):
        assert ".py" in VALID_EXTENSIONS

    def test_js_in_valid_extensions(self):
        assert ".js" in VALID_EXTENSIONS

