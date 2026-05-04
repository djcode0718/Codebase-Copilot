# import os
# from typing import Optional
# from app.ingestion.repo_loader import load_repository
# from app.ingestion.file_filter import filter_files
# from app.parsing.code_parser import parse_code_files
# from app.indexing.index_builder import build_index
# from app.utils.logger import get_logger
# from app.indexing.file_map_builder import build_file_map

# logger = get_logger(__name__)

# def process_repository(source: str) -> Optional[str]:
#     """
#     Orchestrates repository pipeline:
#     load_repository -> filter_files -> parse_code_files -> build_index
#     Returns the name of the index generated or None if failed.
#     """
#     try:
#         logger.info(f"Starting pipeline for source: {source}")
        
#         # 1. Load Repo
#         repo_path = load_repository(source)
        
#         # The index name will be the folder name
#         index_name = os.path.basename(os.path.normpath(repo_path))
        
#         # 2. Filter Files
#         valid_files = filter_files(repo_path)
#         if not valid_files:
#             logger.warning("No valid code files found in the repository.")
#             return None
            
#         # 3. Parse Code Files
#         chunks = parse_code_files(valid_files, repo_path)


#         # 🔥 Build File Map (NEW STEP)
#         build_file_map(valid_files, repo_path, index_name)

#         if not chunks:
#             logger.warning("No chunks generated from the code files.")
#             return None
            
#         # 4. Build Index
#         build_index(chunks, index_name=index_name)
        
#         logger.info(f"Successfully processed repository. Index name: {index_name}")
#         return index_name
        
#     except Exception as e:
#         logger.error(f"Failed to process repository {source}: {e}", exc_info=True)
#         return None


# """
# repo_service.py
# ───────────────
# Orchestrates the full indexing pipeline:

#   load_repository
#       ↓
#   filter_files
#       ↓
#   load_documents  (wrap files in LlamaIndex Document objects)
#       ↓
#   parse_documents (CodeSplitter / SentenceSplitter → Nodes)
#       ↓
#   build_vector_index  (ChromaDB + nomic-embed-text)
#   build_summary_index (DocumentSummaryIndex for file-level retrieval)
#   build_bm25_retriever (keyword retrieval, saved to session state)

# Returns index_name on success, None on failure.
# """

# import os
# from typing import Optional
# from llama_index.core import Settings

# from app.ingestion.repo_loader import load_repository
# from app.ingestion.file_filter import filter_files
# from app.parsing.code_parser import load_documents, parse_documents
# from app.indexing.index_builder import (
#     build_vector_index,
#     build_summary_index,
#     build_bm25_retriever,
# )
# from app.llm.llm_client import get_llm, get_embed_model
# from app.utils.logger import get_logger

# logger = get_logger(__name__)


# def process_repository(source: str) -> Optional[str]:
#     """
#     Full indexing pipeline. Returns index_name (repo folder name) or None.
#     Safe to re-run — ChromaDB and summary index skip re-processing if
#     they already exist on disk for this index_name.
#     """
#     try:
#         # ── 0. Configure LlamaIndex global settings ───────────────────────
#         # Set once here so every downstream component picks them up
#         # automatically without needing explicit llm= / embed_model= args.
#         Settings.llm = get_llm()
#         Settings.embed_model = get_embed_model()

#         logger.info(f"Starting indexing pipeline for: {source}")

#         # ── 1. Clone / validate repo ──────────────────────────────────────
#         repo_path = load_repository(source)
#         index_name = os.path.basename(os.path.normpath(repo_path))

#         # ── 2. Filter files ───────────────────────────────────────────────
#         valid_files = filter_files(repo_path)
#         if not valid_files:
#             logger.warning("No valid code files found.")
#             return None

#         logger.info(f"Found {len(valid_files)} valid files")

#         # ── 3. Load into Documents ────────────────────────────────────────
#         documents = load_documents(valid_files, repo_path)
#         if not documents:
#             logger.warning("No documents loaded.")
#             return None

#         # ── 4. Parse into Nodes ───────────────────────────────────────────
#         nodes = parse_documents(documents)
#         if not nodes:
#             logger.warning("No nodes generated.")
#             return None

#         logger.info(f"Total nodes to index: {len(nodes)}")

#         # ── 5. Build VectorStoreIndex (ChromaDB + nomic-embed-text) ───────
#         build_vector_index(nodes, index_name)

#         # ── 6. Build DocumentSummaryIndex (file-level coarse retrieval) ───
#         build_summary_index(documents, index_name)

#         # ── 7. BM25 is built fresh at query time from loaded nodes ─────────
#         # (BM25Retriever is in-memory, rebuilt in qa_service on each session load)

#         logger.info(f"Pipeline complete. Index name: '{index_name}'")
#         return index_name

#     except Exception as e:
#         logger.error(f"Pipeline failed for '{source}': {e}", exc_info=True)
#         return None

"""
repo_service.py
───────────────
Full indexing pipeline:

  load_repository
      ↓
  filter_files
      ↓
  build_codebase_context    ← NEW: architectural summary document
      ↓
  load_documents + parse_documents
      ↓
  inject context doc into nodes
      ↓
  build_vector_index  (ChromaDB + nomic-embed-text)
  build_summary_index (DocumentSummaryIndex)
"""

import os
from typing import Optional
from llama_index.core import Settings

from app.ingestion.repo_loader import load_repository
from app.ingestion.file_filter import filter_files
from app.parsing.code_parser import load_documents, parse_documents
from app.indexing.context_builder import build_codebase_context
from app.indexing.index_builder import build_vector_index, build_summary_index
from app.llm.llm_client import get_llm, get_embed_model
from app.utils.logger import get_logger

logger = get_logger(__name__)


def process_repository(source: str) -> Optional[str]:
    """
    Full indexing pipeline. Returns index_name on success, None on failure.
    Safe to re-run — ChromaDB, summary index, and context doc are all
    cached to disk and skipped if they already exist.
    """
    try:
        # ── 0. LlamaIndex global settings ─────────────────────────────────
        Settings.llm = get_llm()
        Settings.embed_model = get_embed_model()

        logger.info(f"Starting indexing pipeline for: {source}")

        # ── 1. Clone / validate ────────────────────────────────────────────
        repo_path = load_repository(source)
        index_name = os.path.basename(os.path.normpath(repo_path))

        # ── 2. Filter files ────────────────────────────────────────────────
        valid_files = filter_files(repo_path)
        if not valid_files:
            logger.warning("No valid code files found.")
            return None
        logger.info(f"Found {len(valid_files)} valid files")

        # ── 3. Build codebase context document ────────────────────────────
        # This is the architectural summary injected into the index.
        # Enables broad/creative queries to retrieve high-level context.
        context_doc = build_codebase_context(valid_files, repo_path, index_name)

        # ── 4. Load files into Documents ───────────────────────────────────
        documents = load_documents(valid_files, repo_path)
        if not documents:
            logger.warning("No documents loaded.")
            return None

        # ── 5. Parse into Nodes ────────────────────────────────────────────
        nodes = parse_documents(documents)
        if not nodes:
            logger.warning("No nodes generated.")
            return None

        # ── 6. Parse context doc into nodes and inject ─────────────────────
        # SentenceSplitter handles the summary doc (it's structured text, not code)
        from llama_index.core.node_parser import SentenceSplitter
        context_splitter = SentenceSplitter(chunk_size=768, chunk_overlap=64)
        context_nodes = context_splitter.get_nodes_from_documents([context_doc])
        nodes = context_nodes + nodes   # prepend so it's prioritised in ChromaDB

        logger.info(f"Total nodes to index: {len(nodes)} ({len(context_nodes)} context + {len(nodes) - len(context_nodes)} code)")

        # ── 7. VectorStoreIndex (ChromaDB + nomic-embed-text) ─────────────
        build_vector_index(nodes, index_name)

        # ── 8. DocumentSummaryIndex (file-level coarse retrieval) ──────────
        build_summary_index(documents, index_name)

        logger.info(f"Pipeline complete. Index: '{index_name}'")
        return index_name

    except Exception as e:
        logger.error(f"Pipeline failed for '{source}': {e}", exc_info=True)
        return None