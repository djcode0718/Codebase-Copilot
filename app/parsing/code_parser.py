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

        # Hard cap — protects memory on massive generated files
        content = content[:20000]

        relative_path = Path(os.path.relpath(file_path, repo_path)).as_posix()
        file_name = os.path.basename(file_path)
        ext = Path(file_path).suffix.lower()

        doc = Document(
            text=content,
            metadata={
                "file_name": file_name,
                "path": relative_path,
                "extension": ext,
                "file_size": len(content),
            },
            # Exclude heavy fields from embedding to keep vectors clean
            excluded_embed_metadata_keys=["file_size"],
            excluded_llm_metadata_keys=["file_size", "extension"],
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
        if ext in LANGUAGE_MAP:
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