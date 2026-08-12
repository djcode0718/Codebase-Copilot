"""
index_builder.py
────────────────
Builds two complementary indexes:

1. VectorStoreIndex (ChromaDB + nomic-embed-text)
   Dense semantic search over code chunks.
   Persisted to disk — survives app restarts.

2. DocumentSummaryIndex
   LLM-generated summary per file for coarse file-level retrieval.
   Replaces the old file_map_builder + TF-IDF approach.

3. BM25Retriever (built from the same nodes)
   Keyword/exact-match retrieval — catches function names, variable
   names, and identifiers that dense embeddings often miss.

All three are combined in qa_service.py via QueryFusionRetriever.
"""

import os
import time
from typing import List
from pathlib import Path

import chromadb
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.core.schema import BaseNode
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.retrievers.bm25 import BM25Retriever

from app.config import INDEX_DIR, TOP_K_CHUNKS
from app.llm.llm_client import get_llm, get_embed_model
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_chroma_collection(index_name: str):
    """Return (chroma_client, collection) for a given index name."""
    index_name = (index_name or "").strip()
    if not index_name:
        raise ValueError("index_name cannot be empty")

    chroma_path = os.path.join(INDEX_DIR, index_name, "chroma")
    os.makedirs(chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(index_name)
    return client, collection


def build_vector_index(nodes: List[BaseNode], index_name: str) -> VectorStoreIndex:
    # Explicitly re-set embed model in this thread to prevent
    # LlamaIndex from falling back to an implicit default embed model
    from llama_index.core import Settings
    from app.llm.llm_client import get_embed_model
    if Settings.embed_model is None:
        Settings.embed_model = get_embed_model()

    """
    Embed all nodes with nomic-embed-text and store in ChromaDB.
    ChromaDB persists automatically — subsequent loads skip re-embedding.
    """
    logger.info(f"Building VectorStoreIndex — {len(nodes)} nodes")
    start = time.time()

    _, collection = _get_chroma_collection(index_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    index = VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        show_progress=True,
    )

    logger.info(f"VectorStoreIndex built in {time.time() - start:.2f}s")
    return index


def build_bm25_retriever(nodes: List[BaseNode], top_k: int = TOP_K_CHUNKS) -> BM25Retriever:
    """
    Build an in-memory BM25 retriever over all nodes.
    BM25 is keyword/exact-match — catches identifiers, function names,
    and class names that dense embeddings often score poorly on.
    No GPU, no model weights — pure Python, instant on M4.
    """
    logger.info(f"Building BM25Retriever over {len(nodes)} nodes")
    retriever = BM25Retriever.from_defaults(
        nodes=nodes,
        similarity_top_k=top_k,
    )
    return retriever


def load_vector_index(index_name: str) -> VectorStoreIndex:
    """Load an existing VectorStoreIndex from ChromaDB (no re-embedding)."""
    index_name = (index_name or "").strip()
    if not index_name:
        raise ValueError("index_name cannot be empty")

    _, collection = _get_chroma_collection(index_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    logger.info(f"Loaded VectorStoreIndex '{index_name}' from ChromaDB")
    return index