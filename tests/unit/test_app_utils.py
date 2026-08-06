"""
tests/test_app_utils.py
Unit tests for:
  - app/utils/logger.py  â†’ get_logger()
  - app/utils/helpers.py â†’ clean_directory(), get_file_extension()

Pure Python â€” no LLM, no Supabase, no disk I/O (uses tmp_path).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import logging
import pytest
from app.utils.logger import get_logger
from app.utils.helpers import clean_directory, get_file_extension


# â”€â”€ get_logger â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetLogger:
    def test_returns_logger_instance(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_logger_name_matches(self):
        logger = get_logger("my.custom.module")
        assert logger.name == "my.custom.module"

    def test_logger_has_handlers(self):
        logger = get_logger("test.handlers")
        assert len(logger.handlers) > 0

    def test_logger_level_is_debug(self):
        logger = get_logger("test.level")
        assert logger.level == logging.DEBUG

    def test_handler_is_stream_handler(self):
        logger = get_logger("test.streamhandler")
        assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)

    def test_calling_twice_does_not_duplicate_handlers(self):
        """Handlers should not pile up on repeated calls."""
        logger1 = get_logger("test.idempotent")
        handler_count_after_first = len(logger1.handlers)

        logger2 = get_logger("test.idempotent")
        handler_count_after_second = len(logger2.handlers)

        assert handler_count_after_first == handler_count_after_second

    def test_logger_can_log_without_error(self, capfd):
        logger = get_logger("test.canlog")
        logger.info("This is a test log message")
        captured = capfd.readouterr()
        assert "test log message" in captured.out

    def test_different_names_give_different_loggers(self):
        a = get_logger("module.a")
        b = get_logger("module.b")
        assert a is not b
        assert a.name != b.name


# â”€â”€ get_file_extension â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestGetFileExtension:
    def test_python_file(self):
        assert get_file_extension("main.py") == ".py"

    def test_javascript_file(self):
        assert get_file_extension("app.js") == ".js"

    def test_typescript_file(self):
        assert get_file_extension("component.tsx") == ".tsx"

    def test_uppercase_extension_lowercased(self):
        assert get_file_extension("README.MD") == ".md"

    def test_mixed_case_extension_lowercased(self):
        assert get_file_extension("Script.PY") == ".py"

    def test_no_extension(self):
        assert get_file_extension("Makefile") == ""

    def test_dotfile(self):
        assert get_file_extension(".gitignore") == ""

    def test_file_with_path(self):
        assert get_file_extension("/home/user/project/utils.py") == ".py"

    def test_file_with_multiple_dots(self):
        assert get_file_extension("archive.tar.gz") == ".gz"

    def test_empty_string(self):
        assert get_file_extension("") == ""

    def test_json_file(self):
        assert get_file_extension("package.json") == ".json"

    def test_hidden_file_with_extension(self):
        assert get_file_extension(".env.local") == ".local"


# â”€â”€ clean_directory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestCleanDirectory:
    def test_cleans_files_from_directory(self, tmp_path):
        # Create some files
        (tmp_path / "file1.txt").write_text("hello")
        (tmp_path / "file2.py").write_text("print('hi')")
        assert len(list(tmp_path.iterdir())) == 2

        clean_directory(str(tmp_path))

        assert len(list(tmp_path.iterdir())) == 0

    def test_cleans_subdirectories(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        clean_directory(str(tmp_path))

        assert len(list(tmp_path.iterdir())) == 0

    def test_cleans_mixed_content(self, tmp_path):
        (tmp_path / "a.txt").write_text("file")
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "b.py").write_text("code")

        clean_directory(str(tmp_path))

        assert list(tmp_path.iterdir()) == []

    def test_nonexistent_directory_does_not_raise(self):
        """Should silently do nothing if directory doesn't exist."""
        clean_directory("/tmp/__definitely_does_not_exist_abcxyz__")

    def test_directory_itself_remains_after_clean(self, tmp_path):
        (tmp_path / "file.txt").write_text("content")
        clean_directory(str(tmp_path))
        # The directory itself should still exist, just empty
        assert tmp_path.exists()
        assert tmp_path.is_dir()

    def test_empty_directory_clean_is_noop(self, tmp_path):
        clean_directory(str(tmp_path))
        assert tmp_path.exists()

    def test_symlink_is_removed(self, tmp_path):
        target = tmp_path / "target.txt"
        target.write_text("real file")
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(target)
        except OSError as exc:
            # Windows may require elevated privileges or Developer Mode for symlinks.
            if getattr(exc, "winerror", None) == 1314:
                pytest.skip("Symlink creation requires additional Windows privileges")
            raise

        clean_directory(str(tmp_path))

        assert not link.exists()

