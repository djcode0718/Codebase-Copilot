"""
tests/unit/test_code_parser.py
Unit tests for code_parser.py truncation observability, metadata propagation,
and parsing behavior across file types.
"""
from __future__ import annotations

import logging
import os
import tempfile
import pytest

from app.parsing.code_parser import load_documents, parse_documents


def test_code_parser_module_importable():
    pytest.importorskip("tqdm", reason="tqdm not installed in this environment")
    import app.parsing.code_parser as m
    assert m is not None


def test_source_content_below_cap(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "small.py"
    content = "x = 1\ny = 2\n" * 10  # ~140 chars
    file_path.write_text(content, encoding="utf-8")

    docs = load_documents([str(file_path)], str(repo_dir))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.text == content
    assert doc.metadata["file_size"] == len(content)
    assert doc.metadata["is_truncated"] is False
    assert doc.metadata["file_name"] == "small.py"
    assert doc.metadata["path"] == "small.py"


def test_source_content_exactly_at_cap(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "exact_cap.py"
    content = "a" * 20000
    file_path.write_text(content, encoding="utf-8")

    docs = load_documents([str(file_path)], str(repo_dir))
    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.text) == 20000
    assert doc.text == content
    assert doc.metadata["file_size"] == 20000
    assert doc.metadata["is_truncated"] is False


def test_source_content_exceeding_cap_and_warning_log(tmp_path):
    import io
    from app.parsing.code_parser import logger as parser_logger

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "large.py"
    original_size = 25000
    content = "b" * original_size
    file_path.write_text(content, encoding="utf-8")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.WARNING)
    parser_logger.addHandler(handler)

    try:
        docs = load_documents([str(file_path)], str(repo_dir))
    finally:
        parser_logger.removeHandler(handler)

    assert len(docs) == 1
    doc = docs[0]
    # Retained content length is capped at 20000 chars
    assert len(doc.text) == 20000
    assert doc.text == "b" * 20000

    # Original file size is preserved in metadata
    assert doc.metadata["file_size"] == 25000
    assert doc.metadata["is_truncated"] is True

    # Warning log must record relative path, original size, retained size, and truncation status
    log_output = stream.getvalue()
    assert "File truncated during parsing: path='large.py'" in log_output
    assert "original_size=25000" in log_output
    assert "retained_size=20000" in log_output
    assert "is_truncated=True" in log_output
    # Source content itself must never be dumped into logs
    assert "b" * 100 not in log_output


def test_metadata_preservation_through_document_wrapping(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "config.json"
    content = '{"key1": "value1", "key2": 123}'
    file_path.write_text(content, encoding="utf-8")

    docs = load_documents([str(file_path)], str(repo_dir))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["format"] == "json"
    assert doc.metadata["file_size"] == len(content)
    assert doc.metadata["is_truncated"] is False
    assert "key1" in doc.metadata.get("top_keys", [])
    assert "is_truncated" in doc.excluded_embed_metadata_keys
    assert "file_size" in doc.excluded_embed_metadata_keys


def test_metadata_propagation_into_chunks(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "module.py"
    # Function definitions that will be split by CodeSplitter into nodes
    functions = []
    for i in range(10):
        functions.append(f"def func_{i}():\n    '''Documentation {i}'''\n    x = {i}\n    return x\n")
    content = "\n".join(functions)
    file_path.write_text(content, encoding="utf-8")

    docs = load_documents([str(file_path)], str(repo_dir))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["file_size"] == len(content)
    assert doc.metadata["is_truncated"] is False

    nodes = parse_documents(docs)
    assert len(nodes) > 0
    # Every chunk node should inherit file_size and is_truncated
    for node in nodes:
        assert node.metadata.get("file_size") == len(content)
        assert node.metadata.get("is_truncated") is False
        assert node.metadata.get("file_name") == "module.py"


def test_notebook_metadata_handling(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    file_path = repo_dir / "analysis.ipynb"
    notebook_content = '''{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Header\\n",
    "Explanation text"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 1,
   "metadata": {},
   "outputs": [],
   "source": [
    "import math\\n",
    "print(math.pi)"
   ]
  }
 ],
 "metadata": {
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}'''
    file_path.write_text(notebook_content, encoding="utf-8")

    docs = load_documents([str(file_path)], str(repo_dir))
    assert len(docs) == 2

    md_doc = next(d for d in docs if d.metadata.get("cell_type") == "markdown")
    code_doc = next(d for d in docs if d.metadata.get("cell_type") == "code")

    assert md_doc.metadata["is_truncated"] is False
    assert md_doc.metadata["file_size"] == len(md_doc.text)
    assert code_doc.metadata["is_truncated"] is False
    assert code_doc.metadata["file_size"] == len(code_doc.text)
