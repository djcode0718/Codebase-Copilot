# import os
# import re
# from typing import List, Dict, Any
# from app.parsing.chunk_utils import chunk_text
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# def parse_code_files(file_paths: List[str], repo_path: str) -> List[Dict[str, Any]]:
#     """
#     Reads code files and splits them into chunks.
#     Attaches metadata (file name, path, function/class name if possible).
#     """
#     all_chunks = []
    
#     for file_path in file_paths:
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#         except Exception as e:
#             logger.warning(f"Failed to read file {file_path}: {e}")
#             continue
            
#         if not content.strip():
#             continue

#         if len(content) > 50000:
#             logger.warning(f"Skipping large file: {file_path}")
#             continue

            
#         relative_path = os.path.relpath(file_path, repo_path)
#         file_name = os.path.basename(file_path)
        
#         # Simple heuristic to extract functions/classes for python
#         # A more robust approach would use Tree-sitter, but regex is simpler and meets "simple, readable implementations"
        
#         if file_path.endswith('.py'):
#             chunks = _parse_python_file(content, relative_path, file_name)
#             all_chunks.extend(chunks)
#         else:
#             # Fallback for other languages: fixed-size chunking
#             # raw_chunks = chunk_text(content, max_chunk_size=1500, overlap=300)
#             raw_chunks = chunk_text(content, max_chunk_size=500, overlap=50)
#             for i, text in enumerate(raw_chunks):
#                 all_chunks.append({
#                     "text": text,
#                     "metadata": {
#                         "file_name": file_name,
#                         "path": relative_path,
#                         "entity_name": f"chunk_{i}"
#                     }
#                 })
#     # Limit chunks to avoid memory issues
#     all_chunks = all_chunks[:50]

#     logger.info(f"Generated {len(all_chunks)} chunks from {len(file_paths)} files.")
#     return all_chunks

# def _parse_python_file(content: str, path: str, file_name: str) -> List[Dict[str, Any]]:
#     """
#     Simple parser for python files that tries to chunk by function/class.
#     """
#     # Split by def or class at the start of a line
#     pattern = re.compile(r'^(?=def |class )', re.MULTILINE)
#     parts = pattern.split(content)
    
#     chunks = []
    
#     # The first part might be module-level code/imports
#     if parts and parts[0].strip():
#         # Fallback to text chunking for large module level code
#         module_chunks = chunk_text(parts[0], max_chunk_size=1500)
#         for i, text in enumerate(module_chunks):
#             chunks.append({
#                 "text": text,
#                 "metadata": {
#                     "file_name": file_name,
#                     "path": path,
#                     "entity_name": "module_level"
#                 }
#             })
            
#     for part in parts[1:]:
#         if not part.strip():
#             continue
            
#         # Extract name
#         first_line = part.split('\\n')[0]
#         entity_name = "unknown"
#         match = re.match(r'(?:def|class)\s+([a-zA-Z0-9_]+)', first_line)
#         if match:
#             entity_name = match.group(1)
            
#         # If the function/class is too large, chunk it further
#         part_chunks = chunk_text(part, max_chunk_size=2000, overlap=200)
#         for i, text in enumerate(part_chunks):
#             name = entity_name if i == 0 else f"{entity_name}_part{i}"
#             chunks.append({
#                 "text": text,
#                 "metadata": {
#                     "file_name": file_name,
#                     "path": path,
#                     "entity_name": name
#                 }
#             })
            
#     return chunks


# import os
# from typing import List, Dict, Any
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# def parse_code_files(file_paths: List[str], repo_path: str) -> List[Dict[str, Any]]:
#     """
#     Simplified parser: Treat each file as a single chunk.
#     This avoids memory issues and ensures stability.
#     """
#     all_chunks = []

#     # Limit number of files processed (safety)
#     # file_paths = file_paths[:3]

#     # # prioritize important files first
#     # priority_files = [f for f in file_paths if "readme" in f.lower()]

#     # # take README + few code files
#     # file_paths = priority_files + file_paths[:5]

#     # Prioritize important files
#     priority_files = []
#     other_files = []

#     for f in file_paths:
#         name = f.lower()
#         if "readme" in name or "main" in name or "app" in name:
#             priority_files.append(f)
#         else:
#             other_files.append(f)

#     MAX_FILES = 10
#     file_paths = (priority_files + other_files)[:MAX_FILES]

#     # Take important files first, then rest
#     # file_paths = priority_files + other_files

#     for file_path in file_paths:
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#         except Exception as e:
#             logger.warning(f"Failed to read file {file_path}: {e}")
#             continue

#         if not content.strip():
#             continue

#         # HARD LIMIT content size (very important)
#         content = content[:20000]

#         relative_path = os.path.relpath(file_path, repo_path)
#         file_name = os.path.basename(file_path)

#         chunk = {
#             "text": content,
#             "metadata": {
#                 "file_name": file_name,
#                 "path": relative_path,
#                 "entity_name": "full_file"
#             }
#         }

#         all_chunks.append(chunk)

#     logger.info(f"Generated {len(all_chunks)} chunks from {len(file_paths)} files.")
#     return all_chunks


# import os
# from typing import List, Dict, Any
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# def parse_code_files(file_paths: List[str], repo_path: str) -> List[Dict[str, Any]]:
#     """
#     Simplified parser: Treat each file as a single chunk.
#     This avoids memory issues and ensures stability.
#     """
#     all_chunks = []

#     # Limit number of files processed (safety)
#     file_paths = file_paths[:3]

#     for file_path in file_paths:
#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#         except Exception as e:
#             logger.warning(f"Failed to read file {file_path}: {e}")
#             continue

#         if not content.strip():
#             continue

#         # HARD LIMIT content size (very important)
#         content = content[:20000]

#         relative_path = os.path.relpath(file_path, repo_path)
#         file_name = os.path.basename(file_path)

#         chunk = {
#             "text": content,
#             "metadata": {
#                 "file_name": file_name,
#                 "path": relative_path,
#                 "entity_name": "full_file"
#             }
#         }

#         all_chunks.append(chunk)

#     logger.info(f"Generated {len(all_chunks)} chunks from {len(file_paths)} files.")
#     return all_chunks


# import os
# import re
# from typing import List, Dict, Any
# from app.parsing.chunk_utils import chunk_text
# from app.utils.logger import get_logger
# from tqdm import tqdm
# import time

# logger = get_logger(__name__)


# def parse_code_files(file_paths: List[str], repo_path: str) -> List[Dict[str, Any]]:
#     """
#     Parse files into meaningful chunks.
#     - Python → function/class level
#     - Others → chunk_text
#     """
#     all_chunks = []

#     logger.info(f"Parsing {len(file_paths)} files...")

#     start_time = time.time()

#     for file_path in tqdm(file_paths, desc="Parsing files"):

#         try:
#             with open(file_path, "r", encoding="utf-8") as f:
#                 content = f.read()
#         except Exception as e:
#             logger.warning(f"Failed to read file {file_path}: {e}")
#             continue

#         if not content.strip():
#             continue

#         # HARD LIMIT (protect memory)
#         content = content[:20000]

#         relative_path = os.path.relpath(file_path, repo_path)
#         file_name = os.path.basename(file_path)

#         logger.info(f"Parsing file: {relative_path}")

#         # 🔥 PYTHON FILES → FUNCTION LEVEL SPLIT
#         if file_path.endswith(".py"):
#             chunks = _parse_python_file(content, relative_path, file_name)
#             all_chunks.extend(chunks)

#         # 🔥 MARKDOWN → smaller chunks
#         elif file_path.endswith(".md"):
#             raw_chunks = chunk_text(content, max_chunk_size=800, overlap=100)

#             MAX_CHUNKS_PER_FILE = 15

#             for i, text in enumerate(raw_chunks[:MAX_CHUNKS_PER_FILE]):
#                 all_chunks.append({
#                     "text": text,
#                     "metadata": {
#                         "file_name": file_name,
#                         "path": relative_path,
#                         "entity_name": f"md_chunk_{i}"
#                     }
#                 })

#         # 🔥 OTHER FILES
#         else:
#             # raw_chunks = chunk_text(content, max_chunk_size=1000, overlap=150)
#             raw_chunks = chunk_text(content, max_chunk_size=600, overlap=100)

#             for i, text in enumerate(raw_chunks):
#                 all_chunks.append({
#                     "text": text,
#                     "metadata": {
#                         "file_name": file_name,
#                         "path": relative_path,
#                         "entity_name": f"chunk_{i}"
#                     }
#                 })
#             # logger.info(f"[CHUNKS] {relative_path} → {len(chunks)} chunks")
#             logger.info(f"[CHUNKS] {relative_path} processed")

#     logger.info(f"Generated {len(all_chunks)} chunks from {len(file_paths)} files.")
#     logger.info(f"Parsing completed in {time.time() - start_time:.2f}s")
#     return all_chunks


# # =========================
# # PYTHON PARSER
# # =========================
# def _parse_python_file(content: str, path: str, file_name: str) -> List[Dict[str, Any]]:
#     """
#     Split Python files by functions/classes.
#     """
#     pattern = re.compile(r'^(?=def |class )', re.MULTILINE)
#     parts = pattern.split(content)

#     chunks = []

#     # Module-level code
#     if parts and parts[0].strip():
#         # module_chunks = chunk_text(parts[0], max_chunk_size=1000, overlap=100)
#         module_chunks = chunk_text(parts[0], max_chunk_size=600, overlap=100)

#         for i, text in enumerate(module_chunks):
#             chunks.append({
#                 "text": text,
#                 "metadata": {
#                     "file_name": file_name,
#                     "path": path,
#                     "entity_name": "module_level"
#                 }
#             })

#     for part in parts[1:]:
#         if not part.strip():
#             continue

#         first_line = part.split("\n")[0]

#         entity_name = "unknown"
#         match = re.match(r'(?:def|class)\s+([a-zA-Z0-9_]+)', first_line)
#         if match:
#             entity_name = match.group(1)

#         # part_chunks = chunk_text(part, max_chunk_size=1200, overlap=150)
#         part_chunks = chunk_text(part, max_chunk_size=800, overlap=100)

#         for i, text in enumerate(part_chunks):
#             name = entity_name if i == 0 else f"{entity_name}_part{i}"

#             chunks.append({
#                 "text": text,
#                 "metadata": {
#                     "file_name": file_name,
#                     "path": path,
#                     "entity_name": name
#                 }
#             })

#     return chunks


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

    # 🔥 Code splitting — one CodeSplitter per language
    for lang, docs in code_docs_by_lang.items():
        try:
            from tree_sitter_language_pack import get_parser

            splitter = CodeSplitter(
                language=lang,
                chunk_lines=CHUNK_LINES,
                chunk_lines_overlap=10,
                max_chars=CHUNK_MAX_CHARS,
                parser=get_parser(lang),
            )
            nodes = splitter.get_nodes_from_documents(docs)
            all_nodes.extend(nodes)
            logger.info(f"CodeSplitter [{lang}]: {len(docs)} files → {len(nodes)} nodes")
        except Exception as e:
            # Fallback to sentence splitter if tree-sitter fails for this language
            logger.warning(f"CodeSplitter failed for {lang}: {e} — falling back to SentenceSplitter")
            fallback = SentenceSplitter(chunk_size=512, chunk_overlap=64)
            nodes = fallback.get_nodes_from_documents(docs)
            all_nodes.extend(nodes)

    # 🔥 Markdown splitting
    if markdown_docs:
        md_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        md_nodes = md_splitter.get_nodes_from_documents(markdown_docs)
        all_nodes.extend(md_nodes)
        logger.info(f"SentenceSplitter [markdown]: {len(markdown_docs)} files → {len(md_nodes)} nodes")

    # 🔥 Other files (HTML, shell scripts, etc.)
    if other_docs:
        other_splitter = SentenceSplitter(chunk_size=512, chunk_overlap=64)
        other_nodes = other_splitter.get_nodes_from_documents(other_docs)
        all_nodes.extend(other_nodes)
        logger.info(f"SentenceSplitter [other]: {len(other_docs)} files → {len(other_nodes)} nodes")

    logger.info(
        f"Parsing complete — {len(all_nodes)} total nodes from {len(documents)} documents "
        f"in {time.time() - start_time:.2f}s"
    )
    return all_nodes