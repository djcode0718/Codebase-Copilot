"""
tests/unit/test_notebook_relationship_graph.py
──────────────────────────────────────────────
Unit tests for notebook-aware AST relationship graph building.
"""

import os
import json
import tempfile
import pytest

from app.parsing.relationship_graph import RelationshipGraphBuilder


def test_synthetic_notebook_relationship_graph():
    """
    Test relationship graph with the required synthetic notebook:
    - import librosa
    - import pandas
    - from keras.models import Sequential
    - Conv1D model construction
    - LabelEncoder
    - A custom function definition and invocation
    """
    notebook_content = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Emotion Analysis Pipeline\n", "This notebook trains a Conv1D model."],
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [{"output_type": "stream", "text": ["Loaded\n"]}],
                "source": [
                    "import librosa\n",
                    "import pandas as pd\n",
                    "from keras.models import Sequential\n",
                    "from sklearn.preprocessing import LabelEncoder\n",
                    "from keras.layers import Conv1D, Activation\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": 2,
                "metadata": {},
                "outputs": [],
                "source": [
                    "def custom_feature_extractor(audio_path):\n",
                    "    data, sr = librosa.load(audio_path)\n",
                    "    return data\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": 3,
                "metadata": {},
                "outputs": [],
                "source": [
                    "feat = custom_feature_extractor('sample.wav')\n",
                    "model = Sequential()\n",
                    "model.add(Conv1D(256, 5, padding='same', input_shape=(216, 1)))\n",
                    "model.add(Activation('relu'))\n",
                    "lb = LabelEncoder()\n",
                ],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        nb_path = os.path.join(td, "analysis.ipynb")
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(notebook_content, f)

        builder = RelationshipGraphBuilder(td)
        graph = builder.build_graph([nb_path])

        # 1. Verify module imports are captured
        assert "librosa" in graph
        assert "analysis.ipynb" in graph["librosa"]
        assert "analysis.ipynb[cell_1]" in graph["librosa"]

        assert "pandas" in graph
        assert "analysis.ipynb" in graph["pandas"]
        assert "analysis.ipynb[cell_1]" in graph["pandas"]

        assert "keras.models" in graph
        assert "analysis.ipynb" in graph["keras.models"]

        # 2. Verify imported symbols are captured
        assert "Sequential" in graph
        assert "analysis.ipynb[cell_1]" in graph["Sequential"]
        assert "analysis.ipynb[cell_3]" in graph["Sequential"]

        assert "Conv1D" in graph
        assert "analysis.ipynb[cell_1]" in graph["Conv1D"]
        assert "analysis.ipynb[cell_3]" in graph["Conv1D"]

        assert "LabelEncoder" in graph
        assert "analysis.ipynb[cell_1]" in graph["LabelEncoder"]
        assert "analysis.ipynb[cell_3]" in graph["LabelEncoder"]

        # 3. Verify custom function definition and invocation
        assert "custom_feature_extractor" in graph
        assert "analysis.ipynb[cell_3]" in graph["custom_feature_extractor"]

        # 4. Verify no false relationships invented
        assert "nonexistent_function" not in graph


def test_mixed_python_and_notebook_references():
    """Verify cross-file references between a Python module and a notebook."""
    nb_content = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [],
                "source": [
                    "from utils import load_dataset\n",
                    "data = load_dataset()\n",
                ],
            }
        ],
    }

    with tempfile.TemporaryDirectory() as td:
        py_path = os.path.join(td, "utils.py")
        with open(py_path, "w", encoding="utf-8") as f:
            f.write("def load_dataset():\n    return [1, 2, 3]\n")

        nb_path = os.path.join(td, "notebook.ipynb")
        with open(nb_path, "w", encoding="utf-8") as f:
            json.dump(nb_content, f)

        builder = RelationshipGraphBuilder(td)
        graph = builder.build_graph([py_path, nb_path])

        # notebook.ipynb references load_dataset defined in utils.py
        assert "load_dataset" in graph
        assert "notebook.ipynb[cell_0]" in graph["load_dataset"]
