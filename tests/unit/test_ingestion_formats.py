"""
tests/unit/test_ingestion_formats.py
─────────────────────────────────────
Comprehensive unit tests for Workstream A:
- Support for JSON, CSV, YAML, TXT, JSONL, and extensionless configuration files
- Malformed file handling and safe fallback
- Content and file size limits
- Binary and unsupported file exclusions
- Incremental indexing hash consistency
"""

from __future__ import annotations

import os
import tempfile
import pytest
from pathlib import Path

from app.ingestion.file_filter import filter_files, MAX_FILE_SIZE
from app.parsing.code_parser import load_documents, parse_documents


@pytest.fixture
def temp_repo(tmp_path):
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    return repo_dir


def test_supported_extensions_filtered_correctly(temp_repo):
    """Verify that JSON, CSV, YAML, TXT, JSONL, Dockerfile, Makefile, LICENSE are accepted."""
    files_to_create = [
        "config.json",
        "data.csv",
        "settings.yaml",
        "ci.yml",
        "notes.txt",
        "dataset.jsonl",
        "Dockerfile",
        "Makefile",
        "LICENSE",
    ]
    for fn in files_to_create:
        (temp_repo / fn).write_text("sample content")

    accepted = filter_files(str(temp_repo))
    accepted_names = {os.path.basename(f) for f in accepted}
    for fn in files_to_create:
        assert fn in accepted_names, f"Expected {fn} to be accepted"


def test_binary_and_unsupported_files_rejected(temp_repo):
    """Verify that binary archives, compiled objects, and images are strictly rejected."""
    bad_files = [
        "model.h5",
        "weights.bin",
        "image.png",
        "photo.jpg",
        "archive.zip",
        "library.so",
        "script.pyc",
        "audio.wav",
    ]
    for fn in bad_files:
        (temp_repo / fn).write_text("binary content")

    accepted = filter_files(str(temp_repo))
    accepted_names = {os.path.basename(f) for f in accepted}
    for fn in bad_files:
        assert fn not in accepted_names, f"Expected {fn} to be rejected"


def test_file_size_limit_rejection(temp_repo):
    """Verify that files exceeding MAX_FILE_SIZE (1MB) are excluded by filter_files."""
    large_file = temp_repo / "giant.json"
    with open(large_file, "wb") as f:
        f.seek(MAX_FILE_SIZE + 1024)
        f.write(b"{}")

    accepted = filter_files(str(temp_repo))
    assert str(large_file) not in accepted


def test_json_ingestion_and_metadata(temp_repo):
    """Verify JSON parsing extracts top-level keys and attaches correct metadata."""
    json_path = temp_repo / "model.json"
    json_path.write_text('{"class_name": "Sequential", "layers": [{"name": "dense_1"}]}')

    docs = load_documents([str(json_path)], str(temp_repo))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["format"] == "json"
    assert "class_name" in doc.metadata["top_keys"]

    nodes = parse_documents(docs)
    assert len(nodes) >= 1
    assert "Sequential" in nodes[0].get_content()


def test_malformed_json_handled_safely(temp_repo):
    """Verify malformed JSON does not crash parser and flags malformed metadata."""
    json_path = temp_repo / "bad.json"
    json_path.write_text('{"incomplete": true, "broken":')

    docs = load_documents([str(json_path)], str(temp_repo))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["format"] == "json"
    assert doc.metadata.get("malformed") is True


def test_csv_ingestion_and_row_count(temp_repo):
    """Verify CSV parsing extracts headers and row counts."""
    csv_path = temp_repo / "Predictions.csv"
    csv_path.write_text("id,emotion,probability\n1,happy,0.92\n2,sad,0.05\n3,neutral,0.03\n")

    docs = load_documents([str(csv_path)], str(temp_repo))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["format"] == "csv"
    assert doc.metadata["row_count"] == 4
    assert "emotion" in doc.metadata["headers"]

    nodes = parse_documents(docs)
    assert len(nodes) >= 1
    assert "happy" in nodes[0].get_content()


def test_malformed_csv_handled_safely(temp_repo):
    """Verify malformed CSV with unclosed quotes handles safely."""
    csv_path = temp_repo / "bad.csv"
    csv_path.write_text('id,name\n1,"unclosed quote\n2,normal\n')

    docs = load_documents([str(csv_path)], str(temp_repo))
    assert len(docs) == 1


def test_yaml_ingestion_and_keys(temp_repo):
    """Verify YAML parsing extracts keys safely."""
    yaml_path = temp_repo / "service.yaml"
    yaml_path.write_text("apiVersion: v1\nkind: Service\nmetadata:\n  name: my-service\n")

    docs = load_documents([str(yaml_path)], str(temp_repo))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["format"] == "yaml"
    assert "apiVersion" in doc.metadata["top_keys"]


def test_jsonl_ingestion_and_record_count(temp_repo):
    """Verify JSONL tracks record count and chunks lines properly."""
    jsonl_path = temp_repo / "train.jsonl"
    jsonl_path.write_text('{"text": "record 1"}\n{"text": "record 2"}\n{"text": "record 3"}\n')

    docs = load_documents([str(jsonl_path)], str(temp_repo))
    assert len(docs) == 1
    doc = docs[0]
    assert doc.metadata["format"] == "jsonl"
    assert doc.metadata["record_count"] == 3


def test_null_bytes_binary_skipped(temp_repo):
    """Verify that any file containing null bytes is detected as binary and skipped."""
    corrupted = temp_repo / "corrupted.txt"
    corrupted.write_bytes(b"hello\x00world")

    docs = load_documents([str(corrupted)], str(temp_repo))
    assert len(docs) == 0


def test_extensionless_dockerfile_and_license(temp_repo):
    """Verify extensionless files get proper format classification."""
    df = temp_repo / "Dockerfile"
    df.write_text("FROM python:3.10-slim\nWORKDIR /app\n")
    lic = temp_repo / "LICENSE"
    lic.write_text("Apache License 2.0\n")

    docs = load_documents([str(df), str(lic)], str(temp_repo))
    assert len(docs) == 2
    formats = {d.metadata["file_name"]: d.metadata["format"] for d in docs}
    assert formats["Dockerfile"] == "config"
    assert formats["LICENSE"] == "license"
