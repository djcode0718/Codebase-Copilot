# """
# context_builder.py
# ──────────────────
# Builds a single "Codebase Context Document" at index time.

# This document contains:
#   - Project structure (all file paths)
#   - Per-file LLM summaries
#   - Extracted function/class names per file
#   - Inferred tech stack

# Why this matters:
#   Broad queries like "what are the limitations?" or "how can I improve this?"
#   have no specific code to retrieve. Without this document, retrieval returns
#   nothing useful and the LLM says "not found in code."

#   This document gives the LLM a bird's-eye view of the whole codebase,
#   so architectural questions always have relevant context to work with.

#   It gets embedded like any other node, so it surfaces naturally during
#   ARCHITECTURAL mode retrieval without any special-casing.
# """

# import os
# import re
# import time
# from pathlib import Path
# from typing import List

# from llama_index.core import Document
# from llama_index.core import Settings

# from app.config import INDEX_DIR
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# # File extensions that hint at the tech stack
# TECH_STACK_MAP = {
#     ".py":           "Python",
#     ".js":           "JavaScript",
#     ".ts":           "TypeScript",
#     ".jsx":          "React",
#     ".tsx":          "React/TypeScript",
#     ".java":         "Java",
#     ".go":           "Go",
#     ".rs":           "Rust",
#     ".cpp":          "C++",
#     ".c":            "C",
#     ".cs":           "C#",
#     ".rb":           "Ruby",
#     ".php":          "PHP",
#     ".html":         "HTML",
#     ".css":          "CSS",
#     ".sh":           "Shell",
#     ".dockerfile":   "Docker",
#     ".yaml":         "YAML/Config",
#     ".yml":          "YAML/Config",
#     ".toml":         "TOML/Config",
#     ".md":           "Documentation",
# }


# def _extract_functions_and_classes(content: str, ext: str) -> dict:
#     """Extract top-level function and class names from source code."""
#     result = {"functions": [], "classes": []}

#     if ext == ".py":
#         result["functions"] = re.findall(r'^def\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
#         result["classes"]   = re.findall(r'^class\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
#     elif ext in (".js", ".ts", ".jsx", ".tsx"):
#         result["functions"] = re.findall(r'(?:function\s+|const\s+|let\s+)([a-zA-Z0-9_]+)\s*[=\(]', content)
#         result["classes"]   = re.findall(r'^class\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)

#     # Cap to avoid bloating the summary doc
#     result["functions"] = result["functions"][:20]
#     result["classes"]   = result["classes"][:10]
#     return result


# def _summarize_file(file_path: str, content: str) -> str:
#     """
#     Get a 2-3 line LLM summary of a file.
#     Falls back to first 200 chars if LLM fails.
#     """
#     snippet = "\n".join(content.splitlines()[:60])
#     prompt = (
#         "Summarize this code file in 2-3 sentences. "
#         "Focus on its purpose and responsibilities, not implementation details.\n\n"
#         f"File: {os.path.basename(file_path)}\n\n{snippet}"
#     )
#     try:
#         response = Settings.llm.complete(prompt)
#         return str(response).strip()
#     except Exception as e:
#         logger.warning(f"LLM summary failed for {file_path}: {e}")
#         return " ".join(content[:200].split())


# def build_codebase_context(
#     file_paths: List[str],
#     repo_path: str,
#     index_name: str,
# ) -> Document:
#     """
#     Build a single Document that captures the full codebase architecture.
#     Saved to disk so it's not rebuilt on every restart.
#     Injected into the node list before indexing so it's embedded alongside
#     regular code chunks.

#     Structure of the document:
#       PROJECT OVERVIEW
#       TECH STACK
#       FILE STRUCTURE
#       FILE SUMMARIES (with functions/classes)

#     Returns a LlamaIndex Document ready for embedding.
#     """
#     cache_path = os.path.join(INDEX_DIR, index_name, "codebase_context.txt")
#     os.makedirs(os.path.dirname(cache_path), exist_ok=True)

#     # Return cached version if it exists
#     if os.path.exists(cache_path):
#         logger.info("Loading cached codebase context document...")
#         with open(cache_path, "r", encoding="utf-8") as f:
#             cached_text = f.read()
#         return Document(
#             text=cached_text,
#             metadata={
#                 "file_name": "_codebase_context",
#                 "path": "_codebase_context",
#                 "doc_type": "architectural_summary",
#             },
#             excluded_embed_metadata_keys=["doc_type"],
#         )

#     logger.info(f"Building codebase context document for {len(file_paths)} files...")
#     start = time.time()

#     # ── Tech stack detection ──────────────────────────────────────────────
#     extensions_found = {}
#     for fp in file_paths:
#         ext = Path(fp).suffix.lower()
#         if ext in TECH_STACK_MAP:
#             lang = TECH_STACK_MAP[ext]
#             extensions_found[lang] = extensions_found.get(lang, 0) + 1

#     tech_stack = ", ".join(
#         f"{lang} ({count} files)"
#         for lang, count in sorted(extensions_found.items(), key=lambda x: -x[1])
#     )

#     # ── File structure ────────────────────────────────────────────────────
#     relative_paths = sorted([
#         Path(os.path.relpath(fp, repo_path)).as_posix()
#         for fp in file_paths
#     ])
#     file_structure = "\n".join(f"  {p}" for p in relative_paths)

#     # ── Per-file summaries ────────────────────────────────────────────────
#     file_summaries = []

#     # Prioritize README + main files for summary (others get preview only)
#     def priority(fp):
#         name = fp.lower()
#         if "readme" in name: return 0
#         if "main" in name:   return 1
#         if "app" in name:    return 2
#         return 3

#     sorted_files = sorted(file_paths, key=priority)

#     # LLM summaries for top 15 files, previews for the rest
#     LLM_SUMMARY_LIMIT = 15

#     for i, file_path in enumerate(sorted_files):
#         try:
#             with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
#                 content = f.read()
#         except Exception:
#             continue

#         if not content.strip() or len(content) < 50:
#             continue

#         rel_path = Path(os.path.relpath(file_path, repo_path)).as_posix()
#         ext = Path(file_path).suffix.lower()
#         symbols = _extract_functions_and_classes(content, ext)

#         if i < LLM_SUMMARY_LIMIT:
#             summary = _summarize_file(file_path, content)
#         else:
#             summary = " ".join(content[:150].split())

#         entry = f"\n### {rel_path}\n{summary}"

#         if symbols["classes"]:
#             entry += f"\nClasses: {', '.join(symbols['classes'])}"
#         if symbols["functions"]:
#             entry += f"\nFunctions: {', '.join(symbols['functions'][:10])}"

#         file_summaries.append(entry)

#     summaries_text = "\n".join(file_summaries)

#     # ── Assemble full document ────────────────────────────────────────────
#     repo_name = os.path.basename(os.path.normpath(repo_path))

#     context_text = f"""# Codebase Architectural Overview: {repo_name}

# ## Tech Stack
# {tech_stack}

# ## Project File Structure
# {file_structure}

# ## File Summaries and Responsibilities
# {summaries_text}

# ## Retrieval Note
# This document provides a high-level view of the entire codebase.
# It is used to answer broad questions about architecture, limitations,
# design patterns, and improvement suggestions.
# """

#     # Cache to disk
#     with open(cache_path, "w", encoding="utf-8") as f:
#         f.write(context_text)

#     logger.info(f"Codebase context document built in {time.time() - start:.2f}s")

#     return Document(
#         text=context_text,
#         metadata={
#             "file_name": "_codebase_context",
#             "path": "_codebase_context",
#             "doc_type": "architectural_summary",
#         },
#         excluded_embed_metadata_keys=["doc_type"],
#     )

"""
context_builder.py
──────────────────
Builds a single "Codebase Context Document" at index time.

This document contains:
  - Project structure (all file paths)
  - Extracted function/class names per file
  - Inferred tech stack

Why this matters:
  Broad queries like "what are the limitations?" or "how can I improve this?"
  have no specific code to retrieve. Without this document, retrieval returns
  nothing useful and the LLM says "not found in code."

  This document gives the LLM a bird's-eye view of the whole codebase,
  so architectural questions always have relevant context to work with.

  It gets embedded like any other node, so it surfaces naturally during
  ARCHITECTURAL mode retrieval without any special-casing.

NOTE: LLM_SUMMARY_LIMIT is set to 0.
Per-file LLM summaries were making 1 LLM API call per file at index time,
causing indexing to take 30+ minutes for medium repos.
The context document still captures full file structure, tech stack,
and all function/class names — which is sufficient for architectural retrieval.
BM25 + ColBERT reranking handles the rest.
"""

import os
import re
import time
from pathlib import Path
from typing import List

from llama_index.core import Document
from llama_index.core import Settings

from app.config import INDEX_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)

# File extensions that hint at the tech stack
TECH_STACK_MAP = {
    ".py":           "Python",
    ".js":           "JavaScript",
    ".ts":           "TypeScript",
    ".jsx":          "React",
    ".tsx":          "React/TypeScript",
    ".java":         "Java",
    ".go":           "Go",
    ".rs":           "Rust",
    ".cpp":          "C++",
    ".c":            "C",
    ".cs":           "C#",
    ".rb":           "Ruby",
    ".php":          "PHP",
    ".html":         "HTML",
    ".css":          "CSS",
    ".sh":           "Shell",
    ".dockerfile":   "Docker",
    ".yaml":         "YAML/Config",
    ".yml":          "YAML/Config",
    ".toml":         "TOML/Config",
    ".md":           "Documentation",
}


def _extract_functions_and_classes(content: str, ext: str) -> dict:
    """Extract top-level function and class names from source code."""
    result = {"functions": [], "classes": []}

    if ext == ".py":
        result["functions"] = re.findall(r'^def\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
        result["classes"]   = re.findall(r'^class\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        result["functions"] = re.findall(r'(?:function\s+|const\s+|let\s+)([a-zA-Z0-9_]+)\s*[=\(]', content)
        result["classes"]   = re.findall(r'^class\s+([a-zA-Z0-9_]+)', content, re.MULTILINE)

    # Cap to avoid bloating the summary doc
    result["functions"] = result["functions"][:20]
    result["classes"]   = result["classes"][:10]
    return result


def _summarize_file(file_path: str, content: str) -> str:
    """
    Get a 2-3 line LLM summary of a file.
    Falls back to first 200 chars if LLM fails.
    """
    snippet = "\n".join(content.splitlines()[:60])
    prompt = (
        "Summarize this code file in 2-3 sentences. "
        "Focus on its purpose and responsibilities, not implementation details.\n\n"
        f"File: {os.path.basename(file_path)}\n\n{snippet}"
    )
    try:
        response = Settings.llm.complete(prompt)
        return str(response).strip()
    except Exception as e:
        logger.warning(f"LLM summary failed for {file_path}: {e}")
        return " ".join(content[:200].split())


def build_codebase_context(
    file_paths: List[str],
    repo_path: str,
    index_name: str,
) -> Document:
    """
    Build a single Document that captures the full codebase architecture.
    Saved to disk so it's not rebuilt on every restart.
    Injected into the node list before indexing so it's embedded alongside
    regular code chunks.

    Structure of the document:
      PROJECT OVERVIEW
      TECH STACK
      FILE STRUCTURE
      FILE SUMMARIES (with functions/classes)

    Returns a LlamaIndex Document ready for embedding.
    """
    cache_path = os.path.join(INDEX_DIR, index_name, "codebase_context.txt")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    logger.info(f"Building codebase context document for {len(file_paths)} files...")
    start = time.time()

    # ── Tech stack detection ──────────────────────────────────────────────
    extensions_found = {}
    for fp in file_paths:
        ext = Path(fp).suffix.lower()
        if ext in TECH_STACK_MAP:
            lang = TECH_STACK_MAP[ext]
            extensions_found[lang] = extensions_found.get(lang, 0) + 1

    tech_stack = ", ".join(
        f"{lang} ({count} files)"
        for lang, count in sorted(extensions_found.items(), key=lambda x: -x[1])
    )

    # ── File structure ────────────────────────────────────────────────────
    relative_paths = sorted([
        Path(os.path.relpath(fp, repo_path)).as_posix()
        for fp in file_paths
    ])
    file_structure = "\n".join(f"  {p}" for p in relative_paths)

    # ── Per-file summaries ────────────────────────────────────────────────
    file_summaries = []

    # Prioritize README + main files
    def priority(fp):
        name = fp.lower()
        if "readme" in name: return 0
        if "main" in name:   return 1
        if "app" in name:    return 2
        return 3

    sorted_files = sorted(file_paths, key=priority)

    # FIX: LLM_SUMMARY_LIMIT set to 0.
    # Previously set to 15, meaning up to 15 sequential LLM API calls at index time.
    # Combined with build_summary_index (also removed), this caused 30+ min indexing.
    # All files now get a plain text preview + extracted symbols only.
    # Retrieval quality is not affected — BM25 + ColBERT handles file-level retrieval.
    LLM_SUMMARY_LIMIT = 0

    for i, file_path in enumerate(sorted_files):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        if not content.strip() or len(content) < 50:
            continue

        rel_path = Path(os.path.relpath(file_path, repo_path)).as_posix()
        ext = Path(file_path).suffix.lower()
        symbols = _extract_functions_and_classes(content, ext)

        if i < LLM_SUMMARY_LIMIT:
            summary = _summarize_file(file_path, content)
        else:
            # Plain text preview — fast, no LLM call
            summary = " ".join(content[:150].split())

        entry = f"\n### {rel_path}\n{summary}"

        if symbols["classes"]:
            entry += f"\nClasses: {', '.join(symbols['classes'])}"
        if symbols["functions"]:
            entry += f"\nFunctions: {', '.join(symbols['functions'][:10])}"

        file_summaries.append(entry)

    summaries_text = "\n".join(file_summaries)

    # ── Assemble full document ────────────────────────────────────────────
    repo_name = os.path.basename(os.path.normpath(repo_path))

    context_text = f"""# Codebase Architectural Overview: {repo_name}

## What This Codebase Does
This repository is a codebase Q&A copilot that lets developers ask natural-language questions about any Git repository.
It implements a RAG (Retrieval-Augmented Generation) pipeline that indexes source code and answers queries using retrieved context.
The system uses ChromaDB for dense vector embeddings (nomic-embed-text via Ollama), BM25 for keyword retrieval, and a CrossEncoder (BAAI/bge-reranker-base) for reranking.
Queries are classified by a router into three modes: CODE_LOOKUP (hybrid BM25+dense retrieval for specific function/class questions), ARCHITECTURAL (dense-only retrieval for broad design questions), and RELATIONSHIP (static call-graph lookup for caller/callee questions).
The backend is a FastAPI application using LlamaIndex as the retrieval orchestration layer.
The frontend is a Next.js application. The system supports multiple LLM providers (Gemini, Groq, Ollama) with automatic fallback.

## Tech Stack
{tech_stack}

## Project File Structure
{file_structure}

## File Summaries and Responsibilities
{summaries_text}

## Retrieval Note
This document provides a high-level architectural view of the entire codebase.
It is used to answer broad questions about architecture, limitations,
design patterns, improvement suggestions, and how components interact.
"""

    # Cache to disk
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(context_text)

    logger.info(f"Codebase context document built in {time.time() - start:.2f}s")

    return Document(
        text=context_text,
        metadata={
            "file_name": "_codebase_context",
            "path": "_codebase_context",
            "doc_type": "architectural_summary",
        },
        excluded_embed_metadata_keys=["doc_type"],
    )