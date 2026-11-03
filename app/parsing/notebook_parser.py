"""
app/parsing/notebook_parser.py
──────────────────────────────
Shared utility for parsing Jupyter Notebook (.ipynb) files.
Extracts code and markdown cells, excludes outputs/binaries, normalizes IPython magics,
and preserves cell index and source line mapping.

Used by:
- app/parsing/code_parser.py (ingestion and chunking)
- app/parsing/relationship_graph.py (AST definition & reference extraction)
- app/indexing/context_builder.py (tech stack & symbol discovery)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Limits to prevent memory exhaustion on oversized or pathological notebooks
MAX_NOTEBOOK_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_CELLS_PER_NOTEBOOK = 1000
MAX_CELL_CHARS = 100_000

# Regex matching IPython line magics (%magic, %%cell_magic) and shell commands (!cmd)
# Ensures modulo operators (e.g. `x = a % b` or `"%s" % val`) are NOT touched.
_IPYTHON_LINE_MAGIC_RE = re.compile(r"^(\s*)%(%?[a-zA-Z_][a-zA-Z0-9_]*)(.*)$")
_IPYTHON_SHELL_CMD_RE = re.compile(r"^(\s*)!(?!=)(\s*.*)$")


@dataclass
class NotebookCell:
    cell_index: int
    cell_type: str  # "code" or "markdown"
    source: str     # Original stripped source
    clean_code: str # For code cells: Python-compatible code with magics commented out
    line_count: int


def normalize_ipython_magics(code: str) -> str:
    """
    Neutralizes IPython magics (%cmd, %%cell_magic) and shell commands (!pip)
    by turning them into valid Python comments while strictly preserving line count
    and indentation.
    """
    lines = code.splitlines()
    cleaned_lines = []
    for line in lines:
        magic_match = _IPYTHON_LINE_MAGIC_RE.match(line)
        if magic_match:
            indent, magic_name, rest = magic_match.groups()
            cleaned_lines.append(f"{indent}# [IPython magic neutralized] %{magic_name}{rest}")
            continue

        shell_match = _IPYTHON_SHELL_CMD_RE.match(line)
        if shell_match:
            indent, cmd = shell_match.groups()
            cleaned_lines.append(f"{indent}# [Shell command neutralized] !{cmd}")
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def parse_notebook(content: str, rel_path: str = "") -> List[NotebookCell]:
    """
    Parses a Jupyter Notebook (.ipynb) JSON string and returns a list of NotebookCell objects.
    
    Guarantees:
    - Never throws on malformed JSON; logs warning and returns empty list.
    - Completely ignores cell outputs, execution counts, and binary base64 payloads.
    - Preserves cell index (0-indexed) and line counts.
    - Normalizes code cells so they can be parsed by Python AST or Tree-sitter.
    """
    if not content or not content.strip():
        return []

    if len(content.encode("utf-8", errors="ignore")) > MAX_NOTEBOOK_BYTES:
        logger.warning(f"Notebook {rel_path} exceeds {MAX_NOTEBOOK_BYTES} bytes; skipping.")
        return []

    try:
        data = json.loads(content)
    except Exception as e:
        logger.warning(f"Failed to parse notebook JSON for '{rel_path}': {e}")
        return []

    if not isinstance(data, dict):
        return []

    raw_cells = data.get("cells")
    if not isinstance(raw_cells, list):
        return []

    parsed_cells: List[NotebookCell] = []

    for i, cell in enumerate(raw_cells[:MAX_CELLS_PER_NOTEBOOK]):
        if not isinstance(cell, dict):
            continue

        cell_type = str(cell.get("cell_type", "")).lower()
        if cell_type not in ("code", "markdown"):
            continue

        raw_source = cell.get("source", "")
        if isinstance(raw_source, list):
            source_text = "".join(str(s) for s in raw_source)
        elif isinstance(raw_source, str):
            source_text = raw_source
        else:
            source_text = ""

        # Enforce max chars per cell
        if len(source_text) > MAX_CELL_CHARS:
            source_text = source_text[:MAX_CELL_CHARS]

        if not source_text.strip():
            continue

        if cell_type == "code":
            clean = normalize_ipython_magics(source_text)
        else:
            clean = ""

        lines = source_text.splitlines()
        parsed_cells.append(
            NotebookCell(
                cell_index=i,
                cell_type=cell_type,
                source=source_text,
                clean_code=clean,
                line_count=len(lines) if lines else 1,
            )
        )

    return parsed_cells


def extract_notebook_python_code(content: str, rel_path: str = "") -> str:
    """
    Convenience function that extracts all code cells from a notebook
    into a single unified Python script string. Each cell is prefixed with
    a comment marker identifying its cell index.
    
    Used by AST relationship graph building and static analysis.
    """
    cells = parse_notebook(content, rel_path)
    code_blocks = []
    for c in cells:
        if c.cell_type == "code" and c.clean_code.strip():
            banner = f"# ── Cell {c.cell_index} ({rel_path or 'notebook'}) ──"
            code_blocks.append(f"{banner}\n{c.clean_code}\n")

    return "\n".join(code_blocks)
