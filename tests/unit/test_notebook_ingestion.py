"""
tests/unit/test_notebook_ingestion.py
─────────────────────────────────────
Unit tests for notebook file filtering, document loading, and node parsing.
"""

import os
import json
import tempfile
import pytest

from app.ingestion.file_filter import filter_files
from app.parsing.code_parser import load_documents, parse_documents


def test_file_filter_includes_ipynb_and_ignores_checkpoints():
    """Verify filter_files accepts .ipynb and completely ignores .ipynb_checkpoints."""
    with tempfile.TemporaryDirectory() as td:
        # Create normal files
        py_file = os.path.join(td, "main.py")
        with open(py_file, "w") as f:
            f.write("print('hello')\n")

        nb_file = os.path.join(td, "experiment.ipynb")
        with open(nb_file, "w") as f:
            f.write("{}\n")

        # Create checkpoint directory and file
        chk_dir = os.path.join(td, ".ipynb_checkpoints")
        os.makedirs(chk_dir, exist_ok=True)
        chk_file = os.path.join(chk_dir, "experiment-checkpoint.ipynb")
        with open(chk_file, "w") as f:
            f.write("{}\n")

        valid_files = filter_files(td)
        assert py_file in valid_files
        assert nb_file in valid_files
        assert chk_file not in valid_files
        assert not any(".ipynb_checkpoints" in f for f in valid_files)


def test_load_documents_extracts_code_and_markdown_cells():
    """Verify load_documents converts notebook cells into structured Documents."""
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Analysis\n", "Explaining the experiment."],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [{"output_type": "stream", "text": ["Done\n"]}],
                "source": ["def run():\n", "    return 42\n"],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        nb_path = os.path.join(td, "test_notebook.ipynb")
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f)

        docs = load_documents([nb_path], td)
        assert len(docs) == 2

        md_doc = next(d for d in docs if d.metadata.get("cell_type") == "markdown")
        code_doc = next(d for d in docs if d.metadata.get("cell_type") == "code")

        # Markdown assertions
        assert md_doc.metadata["file_name"] == "test_notebook.ipynb"
        assert md_doc.metadata["path"] == "test_notebook.ipynb"
        assert md_doc.metadata["language"] == "markdown"
        assert md_doc.metadata["cell_index"] == 0
        assert "# Analysis" in md_doc.text

        # Code assertions
        assert code_doc.metadata["file_name"] == "test_notebook.ipynb"
        assert code_doc.metadata["path"] == "test_notebook.ipynb"
        assert code_doc.metadata["language"] == "python"
        assert code_doc.metadata["cell_index"] == 1
        assert "def run():" in code_doc.text
        assert "Done" not in code_doc.text  # Output excluded


def test_parse_documents_splits_notebook_code_and_markdown():
    """Verify parse_documents splits notebook code and markdown cells and preserves metadata."""
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Title\n", "Paragraph one\n\nParagraph two."],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [],
                "source": [
                    "import os\n",
                    "def helper(x):\n",
                    "    return x + 1\n",
                ],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        nb_path = os.path.join(td, "train.ipynb")
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f)

        docs = load_documents([nb_path], td)
        nodes = parse_documents(docs)

        assert len(nodes) >= 2
        # Check metadata preservation on generated nodes
        paths = [n.metadata.get("path") for n in nodes]
        assert all(p == "train.ipynb" for p in paths)
        cell_types = {n.metadata.get("cell_type") for n in nodes}
        assert "markdown" in cell_types
        assert "code" in cell_types


def test_large_notebook_over_20k_characters_loads_successfully():
    """Regression test: verify notebooks exceeding 20k characters are NOT truncated before parsing."""
    # Build a notebook whose JSON exceeds 25,000 characters
    cells = []
    # Cell 0: markdown introduction
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": ["# Extensive Experiment Pipeline\n", "This pipeline contains many detailed cells.\n"],
    })
    # Add multiple large code cells to comfortably exceed 30k chars of raw JSON
    for i in range(1, 15):
        long_comment = f"# Detailed analysis step {i} with extensive parameter documentation\n" * 40
        code_body = f"def step_{i}(data):\n    # Process data step {i}\n    x = {i} * 10\n    return x\n"
        cells.append({
            "cell_type": "code",
            "execution_count": i,
            "metadata": {},
            "outputs": [],
            "source": long_comment + code_body,
        })

    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": cells,
    }

    with tempfile.TemporaryDirectory() as td:
        nb_path = os.path.join(td, "large_experiment.ipynb")
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_data, f)

        file_size = os.path.getsize(nb_path)
        assert file_size > 20000, f"Test fixture must exceed 20k chars, got {file_size}"

        docs = load_documents([nb_path], td)

        # All 15 cells must produce documents; none lost to JSON truncation
        assert len(docs) == 15

        # Verify cell indices are accurate from 0 to 14
        cell_indices = [d.metadata.get("cell_index") for d in docs]
        assert cell_indices == list(range(15))

        # Check line metadata on last cell
        last_doc = docs[-1]
        assert last_doc.metadata.get("line_start") == 1
        assert last_doc.metadata.get("line_end") > 40
        assert "def step_14(data):" in last_doc.text


def test_ordinary_source_file_truncation_remains_at_20k_characters():
    """Verify that ordinary source files are still truncated to 20,000 characters."""
    with tempfile.TemporaryDirectory() as td:
        py_path = os.path.join(td, "massive_source.py")
        # Write 50,000 characters of valid Python comments/code
        with open(py_path, "w", encoding="utf-8") as f:
            f.write("# padding line\n" * 3500)

        assert os.path.getsize(py_path) > 20000

        docs = load_documents([py_path], td)
        assert len(docs) == 1
        assert len(docs[0].text) == 20000
        assert docs[0].metadata.get("file_size") == 20000
