"""
tests/unit/test_notebook_parser.py
───────────────────────────────────
Unit tests for shared Jupyter notebook parser (app/parsing/notebook_parser.py).
"""

import json
import pytest
from app.parsing.notebook_parser import (
    parse_notebook,
    extract_notebook_python_code,
    normalize_ipython_magics,
    NotebookCell,
    MAX_NOTEBOOK_BYTES,
    MAX_CELLS_PER_NOTEBOOK,
)


def test_parse_valid_notebook_cells():
    """Verify code and markdown cells are extracted with correct types and indices."""
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["# Title\n", "Some markdown explanation."],
            },
            {
                "cell_type": "code",
                "execution_count": 5,
                "metadata": {},
                "outputs": [{"output_type": "stream", "text": ["Output text\n"]}],
                "source": ["import numpy as np\n", "a = np.array([1, 2, 3])\n"],
            },
        ],
    }
    content = json.dumps(nb_data)
    cells = parse_notebook(content, "test.ipynb")

    assert len(cells) == 2
    # Cell 0: markdown
    assert cells[0].cell_index == 0
    assert cells[0].cell_type == "markdown"
    assert "# Title" in cells[0].source
    # Cell 1: code
    assert cells[1].cell_index == 1
    assert cells[1].cell_type == "code"
    assert "import numpy as np" in cells[1].clean_code
    assert cells[1].line_count >= 2


def test_excludes_outputs_and_execution_counts():
    """Verify stdout, stderr, image/png base64, and execution count are excluded."""
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {"widgets": {"state": "dangerous_widget_state"}},
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 42,
                "metadata": {},
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "image/png": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                            "text/plain": ["<Figure size 640x480 with 1 Axes>"],
                        },
                    },
                    {
                        "output_type": "error",
                        "ename": "ValueError",
                        "evalue": "Invalid value",
                        "traceback": ["Traceback line 1", "Traceback line 2"],
                    },
                ],
                "source": ["x = 10\n", "print(x)\n"],
            }
        ],
    }
    content = json.dumps(nb_data)
    cells = parse_notebook(content, "analysis.ipynb")

    assert len(cells) == 1
    cell = cells[0]
    assert "iVBORw0KGgo" not in cell.clean_code
    assert "Traceback" not in cell.clean_code
    assert "42" not in cell.clean_code
    assert cell.clean_code.strip() == "x = 10\nprint(x)"


def test_ipython_magic_neutralization():
    """Verify IPython magics are neutralized while preserving indentation and valid Python code."""
    code_lines = [
        "%matplotlib inline",
        "!pip install librosa",
        "%%time",
        "x = 10 % 3  # Python modulo must be preserved",
        'msg = "Value: %s" % x  # Python string format must be preserved',
        "    %time calculate()  # Indented magic",
    ]
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [],
                "source": "\n".join(code_lines),
            }
        ],
    }
    content = json.dumps(nb_data)
    cells = parse_notebook(content, "magics.ipynb")

    assert len(cells) == 1
    clean = cells[0].clean_code

    # Magics neutralized into comments
    assert "# [IPython magic neutralized] %matplotlib inline" in clean
    assert "!pip install librosa" in clean
    assert "# [Shell command neutralized]" in clean
    assert "# [IPython magic neutralized] %%time" in clean
    assert "    # [IPython magic neutralized] %time calculate()" in clean

    # Valid Python operators untouched
    assert "x = 10 % 3  # Python modulo must be preserved" in clean
    assert 'msg = "Value: %s" % x  # Python string format must be preserved' in clean


def test_malformed_notebook_json_handled_gracefully():
    """Verify corrupted, truncated, or invalid JSON does not raise unhandled exceptions."""
    assert parse_notebook("{invalid_json: true", "corrupt.ipynb") == []
    assert parse_notebook("", "empty.ipynb") == []
    assert parse_notebook("[]", "wrong_root_type.ipynb") == []
    assert parse_notebook(json.dumps({"cells": "not_a_list"}), "bad_cells.ipynb") == []
    assert parse_notebook(json.dumps({"cells": [{"cell_type": 123}]}), "bad_cell_type.ipynb") == []


def test_size_and_cell_count_limits():
    """Verify notebooks exceeding limits are capped or rejected."""
    # Exceeding MAX_NOTEBOOK_BYTES
    huge_padding = " " * (MAX_NOTEBOOK_BYTES + 10)
    assert parse_notebook(huge_padding, "huge.ipynb") == []

    # Exceeding cell count cap
    many_cells = [{"cell_type": "code", "metadata": {}, "outputs": [], "source": "x = 1"} for _ in range(MAX_CELLS_PER_NOTEBOOK + 50)]
    nb_data = {"nbformat": 4, "nbformat_minor": 2, "metadata": {}, "cells": many_cells}
    cells = parse_notebook(json.dumps(nb_data), "too_many_cells.ipynb")
    assert len(cells) == MAX_CELLS_PER_NOTEBOOK


def test_extract_notebook_python_code():
    """Verify extract_notebook_python_code concatenates code cells with index banners."""
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": "# Doc header"},
            {"cell_type": "code", "execution_count": 1, "metadata": {}, "outputs": [], "source": "a = 1"},
            {"cell_type": "code", "execution_count": 2, "metadata": {}, "outputs": [], "source": "b = a + 2"},
        ],
    }
    content = json.dumps(nb_data)
    code = extract_notebook_python_code(content, "pipeline.ipynb")

    assert "# ── Cell 1 (pipeline.ipynb) ──" in code
    assert "a = 1" in code
    assert "# ── Cell 2 (pipeline.ipynb) ──" in code
    assert "b = a + 2" in code
    assert "Doc header" not in code


def test_multiline_not_equal_operator_preserved():
    """Verify multiline != comparison lines are preserved and not confused with shell commands."""
    code_lines = [
        "if (",
        "    actual_label",
        "    != expected_label",
        "):",
        "    mismatch = True",
        "!echo 'shell command still neutralized'",
    ]
    nb_data = {
        "nbformat": 4,
        "nbformat_minor": 2,
        "metadata": {},
        "cells": [
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "outputs": [],
                "source": "\n".join(code_lines),
            }
        ],
    }
    content = json.dumps(nb_data)
    cells = parse_notebook(content, "comparison.ipynb")
    clean = cells[0].clean_code

    # != line must be untouched
    assert "    != expected_label" in clean
    assert "# [Shell command neutralized] !=" not in clean

    # True shell command must be neutralized
    assert "# [Shell command neutralized] !echo 'shell command still neutralized'" in clean
