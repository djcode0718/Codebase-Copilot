"""
tests/unit/test_context_builder.py
──────────────────────────────────
Unit tests for the dynamic repository profiler and section-aware context builder:
- Package manifest extraction (pyproject.toml, requirements.txt, package.json, Cargo.toml, go.mod, setup.py, Pipfile)
- Section-aware README parsing with character budgets and noise filtering
- Entrypoint detection and directory hierarchy extraction
- Notebook workflow extraction from markdown cells and imports
- Dynamic codebase context document generation without hardcoded templates
- Zero LLM calls during profiling
"""

from __future__ import annotations

import json
import os
import tempfile
import pytest

from app.indexing.context_builder import (
    extract_manifest_dependencies,
    extract_section_aware_readme,
    _detect_entrypoints,
    _extract_directory_structure,
    _extract_graph_summary,
    build_codebase_context,
    BUDGET_OVERVIEW,
    BUDGET_ARCHITECTURE,
    BUDGET_PIPELINE,
)


def test_context_builder_module_importable():
    import app.indexing.context_builder as m
    assert m is not None


def test_manifest_dependencies_extraction_all_formats():
    """Verify manifest extraction across Python, Node, Rust, and Go manifests."""
    with tempfile.TemporaryDirectory() as td:
        # 1. requirements.txt
        req_path = os.path.join(td, "requirements.txt")
        with open(req_path, "w", encoding="utf-8") as f:
            f.write("fastapi>=0.100.0\nuvicorn[standard]==0.23.0\n# comment line\npytest~=7.4.0\n-r other.txt\n")

        # 2. package.json
        pkg_path = os.path.join(td, "package.json")
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump({
                "name": "frontend",
                "dependencies": {"next": "^14.0.0", "react": "^18.2.0"},
                "devDependencies": {"typescript": "^5.0.0"}
            }, f)

        # 3. pyproject.toml
        pyproject_path = os.path.join(td, "pyproject.toml")
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(
                '[project]\nname = "my-project"\ndependencies = [\n  "pydantic>=2.0",\n  "httpx",\n]\n'
            )

        # 4. Cargo.toml
        cargo_path = os.path.join(td, "Cargo.toml")
        with open(cargo_path, "w", encoding="utf-8") as f:
            f.write('[dependencies]\ntokio = "1.0"\nserde = { version = "1.0", features = ["derive"] }\n')

        # 5. go.mod
        gomod_path = os.path.join(td, "go.mod")
        with open(gomod_path, "w", encoding="utf-8") as f:
            f.write("module example.com/app\n\ngo 1.20\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.0\n\tgo.uber.org/zap v1.24.0\n)\n")

        # 6. setup.py
        setup_path = os.path.join(td, "setup.py")
        with open(setup_path, "w", encoding="utf-8") as f:
            f.write('from setuptools import setup\nsetup(name="pkg", install_requires=["numpy", "scipy>=1.9"])\n')

        # 7. Pipfile
        pipfile_path = os.path.join(td, "Pipfile")
        with open(pipfile_path, "w", encoding="utf-8") as f:
            f.write('[packages]\nrequests = "*"\nflask = ">=2.0"\n')

        files = [req_path, pkg_path, pyproject_path, cargo_path, gomod_path, setup_path, pipfile_path]
        manifests = extract_manifest_dependencies(td, files)

        assert "requirements.txt" in manifests
        assert "fastapi" in manifests["requirements.txt"]
        assert "pytest" in manifests["requirements.txt"]

        assert "package.json" in manifests
        assert "next" in manifests["package.json"]
        assert "typescript" in manifests["package.json"]

        assert "pyproject.toml" in manifests
        assert "pydantic" in manifests["pyproject.toml"]
        assert "httpx" in manifests["pyproject.toml"]

        assert "Cargo.toml" in manifests
        assert "tokio" in manifests["Cargo.toml"]
        assert "serde" in manifests["Cargo.toml"]

        assert "go.mod" in manifests
        assert "github.com/gin-gonic/gin" in manifests["go.mod"]

        assert "setup.py" in manifests
        assert "numpy" in manifests["setup.py"]

        assert "Pipfile" in manifests
        assert "requests" in manifests["Pipfile"]


def test_section_aware_readme_extraction():
    """Verify section extraction, badge removal, section routing, and budget enforcement."""
    readme_content = """# Awesome Speech Analyzer
[![CI](https://github.com/org/repo/actions/workflows/ci.yml/badge.svg)](https://github.com/org/repo)
<img src="logo.png" width="100"/>

Awesome Speech Analyzer is an end-to-end deep learning framework for classifying human emotion from voice audio.

## Architecture
The system consists of three primary tiers:
1. Feature extraction using Librosa to compute MFCC spectrograms.
2. 1D Convolutional Neural Network trained via Keras.
3. FastAPI inference backend for real-time wav stream classification.

## Training Pipeline & Usage
Run the training script using:
```bash
python train.py --epochs 50 --batch 32
```
Or open the `Speech_Emotion_Analyzer.ipynb` notebook to inspect the confusion matrix.

## License
MIT License. Free for commercial and research use.

## Contributing
Please submit PRs against the main branch.
"""

    with tempfile.TemporaryDirectory() as td:
        readme_path = os.path.join(td, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        sections = extract_section_aware_readme(td, [readme_path])

        # Overview should capture introductory text and exclude badges
        assert "Awesome Speech Analyzer is an end-to-end deep learning framework" in sections["overview"]
        assert "badge.svg" not in sections["overview"]
        assert "<img" not in sections["overview"]

        # Architecture section should be cleanly routed
        assert "Feature extraction using Librosa" in sections["architecture"]
        assert "1D Convolutional Neural Network" in sections["architecture"]

        # Pipeline section should capture usage / training
        assert "python train.py" in sections["pipeline"]

        # Excluded sections must not appear
        assert "MIT License" not in sections["overview"]
        assert "MIT License" not in sections["architecture"]
        assert "MIT License" not in sections["pipeline"]
        assert "submit PRs" not in sections["pipeline"]

        # Ensure budget constraints are respected
        assert len(sections["overview"]) <= BUDGET_OVERVIEW
        assert len(sections["architecture"]) <= BUDGET_ARCHITECTURE
        assert len(sections["pipeline"]) <= BUDGET_PIPELINE


def test_entrypoint_detection_and_directory_structure():
    """Verify entry points and module tree formatting."""
    with tempfile.TemporaryDirectory() as td:
        main_py = os.path.join(td, "main.py")
        app_py = os.path.join(td, "app", "app.py")
        helper_py = os.path.join(td, "app", "helper.py")
        test_py = os.path.join(td, "tests", "test_app.py")

        os.makedirs(os.path.join(td, "app"), exist_ok=True)
        os.makedirs(os.path.join(td, "tests"), exist_ok=True)

        for p in [main_py, app_py, helper_py, test_py]:
            with open(p, "w") as f:
                f.write("# dummy\n")

        files = [main_py, app_py, helper_py, test_py]
        entrypoints = _detect_entrypoints(td, files)

        assert "main.py" in entrypoints
        assert "app/app.py" in entrypoints
        assert "app/helper.py" not in entrypoints

        structure = _extract_directory_structure(td, files)
        assert "app/ (2 files)" in structure
        assert "tests/ (1 files)" in structure
        assert "<root>/ (1 files)" in structure


def test_build_codebase_context_dynamic_no_hardcoded_copilot():
    """Verify that build_codebase_context produces a dynamic document without hardcoded Copilot text."""
    with tempfile.TemporaryDirectory() as td:
        # Create a sample project representing Speech-Emotion-Analyzer
        readme_path = os.path.join(td, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# Speech Emotion Analyzer\nClassifies emotions (happy, sad, angry) from speech recordings using CNNs.\n")

        req_path = os.path.join(td, "requirements.txt")
        with open(req_path, "w", encoding="utf-8") as f:
            f.write("librosa>=0.8.0\nkeras>=2.4.0\ntensorflow>=2.3.0\n")

        main_path = os.path.join(td, "main.py")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write("def predict_emotion(wav_path):\n    pass\n\ndef load_wav_file(path):\n    pass\n")

        # Create a sample notebook
        nb_path = os.path.join(td, "model_training.ipynb")
        nb_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": ["# Emotion Model Training Pipeline\n", "Evaluate Conv1D accuracy."]
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [],
                    "source": ["import librosa\n", "from keras.layers import Conv1D\n"]
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        }
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_content, f)

        files = [readme_path, req_path, main_path, nb_path]

        # Mock graph summary
        mock_graph = {
            "predict_emotion": ["main.py:test_eval", "model_training.ipynb[cell_1]"],
            "librosa": ["main.py", "model_training.ipynb[cell_1]"],
        }

        doc = build_codebase_context(
            file_paths=files,
            repo_path=td,
            index_name="test_speech_repo",
            graph_summary=mock_graph,
        )

        text = doc.get_content()

        # 1. MUST NOT contain hardcoded CodeBase-Copilot self-descriptions
        assert "This repository is a codebase Q&A copilot" not in text
        assert "FastAPI application using LlamaIndex as the retrieval orchestration layer" not in text
        assert "The frontend is a Next.js application" not in text

        # 2. MUST contain dynamic repository identity
        assert "Speech Emotion Analyzer" in text
        assert "Classifies emotions" in text

        # 3. MUST contain manifest dependencies
        assert "librosa" in text
        assert "keras" in text
        assert "requirements.txt" in text

        # 4. MUST contain notebook workflow extraction
        assert "model_training.ipynb" in text
        assert "Emotion Model Training Pipeline" in text

        # 5. MUST contain entry point
        assert "`main.py`" in text

        # 6. MUST contain relationship graph summary
        assert "`predict_emotion`" in text

        # 7. Document metadata must preserve Phase 1 contract
        assert doc.metadata.get("path") == "_codebase_context"
        assert doc.metadata.get("file_name") == "_codebase_context"
        assert doc.metadata.get("doc_type") == "architectural_summary"


def test_readme_budget_truncation_and_malformed_manifests():
    """Verify that oversized README sections are cleanly capped and malformed manifests do not crash."""
    with tempfile.TemporaryDirectory() as td:
        # Create an oversized README
        huge_text = "Word " * 1000  # 5,000 chars
        readme_content = f"# Big Project\n\n## Overview\n{huge_text}\n\n## Architecture\n{huge_text}\n"
        readme_path = os.path.join(td, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        # Create malformed manifests
        bad_json = os.path.join(td, "package.json")
        with open(bad_json, "w", encoding="utf-8") as f:
            f.write("{invalid json")

        bad_pyproject = os.path.join(td, "pyproject.toml")
        with open(bad_pyproject, "w", encoding="utf-8") as f:
            f.write("[project\ninvalid toml")

        sections = extract_section_aware_readme(td, [readme_path])
        assert len(sections["overview"]) <= BUDGET_OVERVIEW
        assert len(sections["architecture"]) <= BUDGET_ARCHITECTURE

        # extract_manifest_dependencies should gracefully return empty dict for malformed manifests
        manifests = extract_manifest_dependencies(td, [bad_json, bad_pyproject])
        assert manifests.get("package.json") is None or manifests.get("package.json") == []
        assert manifests.get("pyproject.toml") is None or manifests.get("pyproject.toml") == []

        # build_codebase_context should succeed without errors
        doc = build_codebase_context([readme_path], td, "test_huge_repo")
        assert doc is not None
        assert doc.metadata.get("path") == "_codebase_context"
