"""
code_parser.py
──────────────
Converts filtered file paths into LlamaIndex Document objects,
then splits them into nodes using CodeSplitter (tree-sitter backed)
for Python/JS/TS/etc., and SentenceSplitter for Markdown and others.

This replaces the old regex-based _parse_python_file + chunk_text approach.
CodeSplitter understands language syntax — it won't split inside a function.
"""

import os
import time
from typing import List
from pathlib import Path
from tqdm import tqdm

from llama_index.core import Document
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter

from app.config import CHUNK_LINES, CHUNK_MAX_CHARS
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Map file extensions to tree-sitter language names
LANGUAGE_MAP = {
    ".py":   "python",
    ".js":   "javascript",
    ".ts":   "typescript",
    ".java": "java",
    ".cpp":  "cpp",
    ".c":    "c",
    ".go":   "go",
    ".rs":   "rust",
    ".rb":   "ruby",
    ".cs":   "c_sharp",
}


def load_documents(file_paths: List[str], repo_path: str) -> List[Document]:
    """
    Read files from disk and wrap each in a LlamaIndex Document.
    Metadata attached here is preserved all the way through to the
    final retrieved nodes — used for citation in the LLM prompt.
    """
    documents = []
    start_time = time.time()

    logger.info(f"Loading {len(file_paths)} files into Documents...")

    for file_path in tqdm(file_paths, desc="Loading files"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            continue

        if not content.strip():
            continue

        relative_path = Path(os.path.relpath(file_path, repo_path)).as_posix()
        file_name = os.path.basename(file_path)
        ext = Path(file_path).suffix.lower()

        if ext == ".ipynb":
            try:
                from app.parsing.notebook_parser import parse_notebook
                cells = parse_notebook(content, relative_path)
                for cell in cells:
                    if cell.cell_type == "code":
                        if not cell.clean_code.strip():
                            continue
                        doc = Document(
                            text=cell.clean_code,
                            metadata={
                                "file_name": file_name,
                                "path": relative_path,
                                "extension": ext,
                                "language": "python",
                                "cell_type": "code",
                                "cell_index": cell.cell_index,
                                "line_start": 1,
                                "line_end": cell.line_count,
                                "file_size": len(cell.clean_code),
                            },
                            excluded_embed_metadata_keys=["file_size"],
                            excluded_llm_metadata_keys=["file_size"],
                        )
                        documents.append(doc)
                    elif cell.cell_type == "markdown":
                        if not cell.source.strip():
                            continue
                        doc = Document(
                            text=cell.source,
                            metadata={
                                "file_name": file_name,
                                "path": relative_path,
                                "extension": ext,
                                "language": "markdown",
                                "cell_type": "markdown",
                                "cell_index": cell.cell_index,
                                "line_start": 1,
                                "line_end": cell.line_count,
                                "file_size": len(cell.source),
                            },
                            excluded_embed_metadata_keys=["file_size"],
                            excluded_llm_metadata_keys=["file_size"],
                        )
                        documents.append(doc)
            except Exception as e:
                logger.warning(f"Failed to parse notebook {file_path}: {e}")
            continue

        # Binary check: reject if null bytes detected
        if "\x00" in content:
            logger.debug(f"Skipping binary file with null bytes: {file_path}")
            continue

        format_type = "code"
        extra_meta = {}

        if ext == ".json":
            format_type = "json"
            try:
                import json as _json
                _parsed = _json.loads(content)
                if isinstance(_parsed, dict):
                    extra_meta["top_keys"] = list(_parsed.keys())[:20]
            except Exception as ex:
                logger.debug("Malformed JSON in %s: %s", relative_path, ex)
                extra_meta["malformed"] = True
        elif ext == ".jsonl":
            format_type = "jsonl"
            lines = content.splitlines()
            valid_count = 0
            for line in lines:
                if line.strip():
                    valid_count += 1
            extra_meta["record_count"] = valid_count
        elif ext == ".csv":
            format_type = "csv"
            try:
                import csv, io
                reader = csv.reader(io.StringIO(content))
                rows = list(reader)
                if rows:
                    extra_meta["headers"] = [str(h).strip() for h in rows[0][:15]]
                    extra_meta["row_count"] = len(rows)
            except Exception as ex:
                logger.debug("Malformed CSV in %s: %s", relative_path, ex)
                extra_meta["malformed"] = True
        elif ext in (".yaml", ".yml"):
            format_type = "yaml"
            try:
                import yaml as _yaml
                _parsed = _yaml.safe_load(content)
                if isinstance(_parsed, dict):
                    extra_meta["top_keys"] = list(_parsed.keys())[:20]
            except Exception as ex:
                logger.debug("Malformed YAML in %s: %s", relative_path, ex)
                extra_meta["malformed"] = True
        elif ext == ".txt":
            format_type = "text"
        elif not ext:
            lower_name = file_name.lower()
            if "license" in lower_name:
                format_type = "license"
            elif "dockerfile" in lower_name or "makefile" in lower_name:
                format_type = "config"
            else:
                format_type = "config"

        # Hard cap — protects memory on massive generated files
        content = content[:20000]

        meta = {
            "file_name": file_name,
            "path": relative_path,
            "extension": ext,
            "format": format_type,
            "file_size": len(content),
        }
        meta.update(extra_meta)

        doc = Document(
            text=content,
            metadata=meta,
            # Exclude heavy fields from embedding to keep vectors clean
            excluded_embed_metadata_keys=["file_size", "top_keys", "headers"],
            excluded_llm_metadata_keys=["file_size", "extension", "top_keys", "headers"],
        )
        documents.append(doc)

    logger.info(
        f"Loaded {len(documents)} documents from {len(file_paths)} files "
        f"in {time.time() - start_time:.2f}s"
    )
    return documents


def parse_documents(documents: List[Document]) -> List:
    """
    Split Documents into Nodes using the appropriate splitter per language:
    - Code files  → CodeSplitter (tree-sitter, syntax-aware)
    - Markdown    → SentenceSplitter (paragraph-aware)
    - Other text  → SentenceSplitter (fallback)

    Returns a flat list of BaseNode objects ready for indexing.
    """
    all_nodes = []
    start_time = time.time()

    # Group documents by splitter type
    code_docs = []
    code_docs_by_lang = {}
    markdown_docs = []
    other_docs = []

    for doc in documents:
        ext = doc.metadata.get("extension", "")
        cell_type = doc.metadata.get("cell_type", "")

        if ext == ".ipynb":
            if cell_type == "code":
                code_docs_by_lang.setdefault("python", []).append(doc)
            elif cell_type == "markdown":
                markdown_docs.append(doc)
            else:
                other_docs.append(doc)
        elif ext in LANGUAGE_MAP:
            lang = LANGUAGE_MAP[ext]
            code_docs_by_lang.setdefault(lang, []).append(doc)
        elif ext == ".md":
            markdown_docs.append(doc)
        else:
            other_docs.append(doc)

    # Code splitting - one CodeSplitter per language
    for lang, docs in code_docs_by_lang.items():
        try:
            splitter = CodeSplitter(
                language=lang,
                chunk_lines=CHUNK_LINES,
                chunk_lines_overlap=10,
                max_chars=CHUNK_MAX_CHARS,
            )
            nodes = splitter.get_nodes_from_documents(docs)
            all_nodes.extend(nodes)
            logger.info(f"CodeSplitter [{lang}]: {len(docs)} files -> {len(nodes)} nodes")
        except Exception as e:
            # Fallback to sentence splitter if CodeSplitter fails for this language.
            logger.warning(f"CodeSplitter failed for {lang}: {e}; falling back to SentenceSplitter")
            fallback = SentenceSplitter(chunk_size=512, chunk_overlap=64)
            nodes = fallback.get_nodes_from_documents(docs)
            all_nodes.extend(nodes)

    # Markdown splitting
    if markdown_docs:
        md_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        md_nodes = md_splitter.get_nodes_from_documents(markdown_docs)
        all_nodes.extend(md_nodes)
        logger.info(f"SentenceSplitter [markdown]: {len(markdown_docs)} files -> {len(md_nodes)} nodes")

    # Other files (HTML, shell scripts, etc.)
    if other_docs:
        other_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        other_nodes = other_splitter.get_nodes_from_documents(other_docs)
        all_nodes.extend(other_nodes)
        logger.info(f"SentenceSplitter [other]: {len(other_docs)} files -> {len(other_nodes)} nodes")

    logger.info(
        f"Parsing complete -- {len(all_nodes)} total nodes from {len(documents)} documents "
        f"in {time.time() - start_time:.2f}s"
    )
    return all_nodes