"""
tests/unit/test_relationship_graph_atomic.py
────────────────────────────────────────────
Unit tests for atomic relationship graph generation and validation:
- Valid serialization and atomic replacement via os.replace
- Staging temp file cleanup on success and failure
- Preservation of pre-existing relationship_graph.json if validation fails
- validate_relationship_graph_file behavior on malformed or empty files
"""

from __future__ import annotations

import json
import os
import tempfile
import pytest
from unittest.mock import patch

from app.parsing.relationship_graph import (
    RelationshipGraphBuilder,
    validate_relationship_graph_file,
)


def test_validate_relationship_graph_file():
    with tempfile.TemporaryDirectory() as td:
        valid_path = os.path.join(td, "valid.json")
        with open(valid_path, "w", encoding="utf-8") as f:
            json.dump({"symbol_a": ["file1.py:fn_a"], "symbol_b": []}, f)
        assert validate_relationship_graph_file(valid_path) is True

        empty_path = os.path.join(td, "empty.json")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")
        assert validate_relationship_graph_file(empty_path) is False

        malformed_path = os.path.join(td, "malformed.json")
        with open(malformed_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        assert validate_relationship_graph_file(malformed_path) is False

        non_dict_path = os.path.join(td, "non_dict.json")
        with open(non_dict_path, "w", encoding="utf-8") as f:
            json.dump(["not", "a", "dict"], f)
        assert validate_relationship_graph_file(non_dict_path) is False

        invalid_val_path = os.path.join(td, "invalid_val.json")
        with open(invalid_val_path, "w", encoding="utf-8") as f:
            json.dump({"symbol": "not a list"}, f)
        assert validate_relationship_graph_file(invalid_val_path) is False

        assert validate_relationship_graph_file(os.path.join(td, "nonexistent.json")) is False


def test_build_graph_atomic_success():
    with tempfile.TemporaryDirectory() as td:
        py_file = os.path.join(td, "module.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("def helper():\n    pass\n\ndef main():\n    helper()\n")

        builder = RelationshipGraphBuilder(td)
        graph, final_path = builder.build_graph_atomic([py_file], td)

        assert os.path.isfile(final_path)
        assert "helper" in graph
        assert validate_relationship_graph_file(final_path) is True

        # Verify no stray temp files left behind
        temp_files = [f for f in os.listdir(td) if f.startswith("relationship_graph.json.tmp_")]
        assert len(temp_files) == 0


def test_build_graph_atomic_preserves_existing_on_validation_failure():
    with tempfile.TemporaryDirectory() as td:
        final_path = os.path.join(td, "relationship_graph.json")
        original_graph = {"original_sym": ["orig.py:scope"]}
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(original_graph, f)

        py_file = os.path.join(td, "module.py")
        with open(py_file, "w", encoding="utf-8") as f:
            f.write("def new_func():\n    pass\n")

        builder = RelationshipGraphBuilder(td)

        # Mock validate_relationship_graph_file to simulate validation failure on temp file
        with patch("app.parsing.relationship_graph.validate_relationship_graph_file", return_value=False):
            with pytest.raises(ValueError, match="failed validation"):
                builder.build_graph_atomic([py_file], td)

        # Existing target file MUST remain untouched
        assert os.path.isfile(final_path)
        with open(final_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == original_graph

        # Temp file must be cleaned up
        temp_files = [f for f in os.listdir(td) if f.startswith("relationship_graph.json.tmp_")]
        assert len(temp_files) == 0


def test_build_graph_atomic_preserves_existing_on_generation_exception():
    with tempfile.TemporaryDirectory() as td:
        final_path = os.path.join(td, "relationship_graph.json")
        original_graph = {"stable_sym": ["stable.py"]}
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(original_graph, f)

        builder = RelationshipGraphBuilder(td)

        with patch.object(builder, "build_graph", side_effect=RuntimeError("AST parser crashed")):
            with pytest.raises(RuntimeError, match="AST parser crashed"):
                builder.build_graph_atomic(["some_file.py"], td)

        # Existing file preserved
        with open(final_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == original_graph
