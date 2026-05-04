# from typing import List, Dict, Any
# import numpy as np
# # from sentence_transformers import SentenceTransformer
# from sklearn.feature_extraction.text import TfidfVectorizer
# from app.indexing.vector_store import VectorStore
# from app.config import EMBEDDING_MODEL
# from app.utils.logger import get_logger
# import time
# from tqdm import tqdm

# logger = get_logger(__name__)

# def build_index(chunks: List[Dict[str, Any]], index_name: str = "default") -> VectorStore:
#     """
#     Converts chunks into embeddings and stores them using vector store.
#     """
#     if not chunks:
#         logger.warning("No chunks provided to build_index.")
#         return None
#         # return VectorStore(index_name)
        
#     logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
#     # model = SentenceTransformer(EMBEDDING_MODEL)
#     # model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    
#     # # We will get the dimension from the model output dynamically if possible,
#     # # but the default VectorStore initialization uses 384 which fits all-MiniLM-L6-v2.
#     # dummy_embedding = model.encode("test")
#     # dimension = len(dummy_embedding)

    
#     # Extract texts for embedding
#     texts = [chunk["text"] for chunk in chunks]
    
#     vectorizer = TfidfVectorizer(max_features=512)
#     embeddings = vectorizer.fit_transform(texts).toarray()
#     dimension = embeddings.shape[1]
    
#     vector_store = VectorStore(index_name, dimension=dimension)

#     # Generate embeddings
#     # logger.info(f"Generating embeddings for {len(texts)} chunks...")
#     # embeddings = model.encode(texts, show_progress_bar=True)

#     # embeddings = []

#     # BATCH_SIZE = 8  # small batch to avoid memory spike

#     # for i in range(0, len(texts), BATCH_SIZE):
#     #     batch = texts[i:i + BATCH_SIZE]
#     #     batch_embeddings = model.encode(batch, show_progress_bar=False)
#     #     embeddings.extend(batch_embeddings)
    
#     # Add to store
#     # vector_store.add_embeddings(np.array(embeddings), chunks)
#     # vector_store.save()
    
#     # logger.info(f"Index built and saved successfully as '{index_name}'.")
#     # return vector_store
#     # IMPORTANT: store vectorizer for retrieval 
#     vector_store.vectorizer = vectorizer

#     logger.info(f"Generating embeddings for {len(texts)} chunks...")

#     vector_store.add_embeddings(np.array(embeddings), chunks)
#     logger.info(f"Index built and saved successfully as '{index_name}'.")
#     vector_store.save()



# from typing import List, Dict, Any
# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from app.indexing.vector_store import VectorStore
# from app.config import EMBEDDING_MODEL
# from app.utils.logger import get_logger
# import time
# from tqdm import tqdm

# logger = get_logger(__name__)


# def build_index(chunks: List[Dict[str, Any]], index_name: str = "default") -> VectorStore:
#     """
#     Converts chunks into embeddings and stores them using vector store.
#     """

#     if not chunks:
#         logger.warning("No chunks provided to build_index.")
#         return None

#     logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")

#     # 🔹 Extract texts
#     texts = [chunk["text"] for chunk in chunks]

#     # 🔹 Initialize vectorizer
#     vectorizer = TfidfVectorizer(
#         max_features=1000,
#         stop_words="english",
#         lowercase=True
#     )

#     # 🔥 STEP 1: FIT + TRANSFORM (CRITICAL)
#     start_time = time.time()
#     logger.info("Fitting vectorizer and generating embeddings...")

#     embeddings = vectorizer.fit_transform(texts).toarray()

#     logger.info(f"Embedding generation completed in {time.time() - start_time:.2f}s")

#     # 🔹 Optional: Per-chunk logging (NO recomputation)
#     # for chunk in tqdm(chunks, desc="Logging embeddings"):
#     #     logger.debug(f"Embedded: {chunk['metadata']['path']}")

#     # 🔹 Get dimension
#     dimension = embeddings.shape[1]

#     # 🔹 Initialize vector store
#     vector_store = VectorStore(index_name, dimension=dimension)

#     # 🔹 Store vectorizer (IMPORTANT)
#     vector_store.vectorizer = vectorizer

#     # 🔹 Add embeddings
#     vector_store.add_embeddings(np.array(embeddings), chunks)

#     # 🔹 Save index
#     vector_store.save()

#     logger.info(f"Index built and saved successfully as '{index_name}'.")

#     return vector_store

# from typing import List, Dict, Any
# import numpy as np
# from sklearn.feature_extraction.text import TfidfVectorizer
# from app.indexing.vector_store import VectorStore
# from app.utils.logger import get_logger
# import time

# logger = get_logger(__name__)


# def build_index(chunks: List[Dict[str, Any]], index_name: str = "default") -> VectorStore:
#     """
#     Converts parsed code chunks into TF-IDF embeddings and saves them
#     to the vector store. This will be replaced by nomic-embed-text
#     dense embeddings in the LlamaIndex migration.
#     """

#     if not chunks:
#         logger.warning("No chunks provided to build_index.")
#         return None

#     # 🔹 Extract texts
#     texts = [chunk["text"] for chunk in chunks]

#     logger.info(f"Building TF-IDF index for {len(texts)} chunks...")

#     # 🔹 Fit vectorizer
#     vectorizer = TfidfVectorizer(
#         max_features=1000,
#         stop_words="english",
#         lowercase=True
#     )

#     start_time = time.time()
#     embeddings = vectorizer.fit_transform(texts).toarray()
#     logger.info(f"Vectorization completed in {time.time() - start_time:.2f}s")

#     dimension = embeddings.shape[1]

#     # 🔹 Initialize and populate vector store
#     vector_store = VectorStore(index_name, dimension=dimension)
#     vector_store.vectorizer = vectorizer
#     vector_store.add_embeddings(np.array(embeddings), chunks)

#     # 🔹 Persist to disk
#     vector_store.save()

#     logger.info(f"Index '{index_name}' built and saved — {len(chunks)} chunks, dimension={dimension}.")

#     return vector_store


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
    DocumentSummaryIndex,
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
    chroma_path = os.path.join(INDEX_DIR, index_name, "chroma")
    os.makedirs(chroma_path, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_or_create_collection(index_name)
    return client, collection


def build_vector_index(nodes: List[BaseNode], index_name: str) -> VectorStoreIndex:
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


def build_summary_index(documents, index_name: str) -> DocumentSummaryIndex:
    """
    Build a DocumentSummaryIndex — LLM writes a summary for each file.
    Used for coarse file-level retrieval before dense chunk search.
    Replaces the old file_map_builder + TF-IDF file summaries.

    Summaries are persisted to disk and reused on subsequent runs.
    """
    summary_path = os.path.join(INDEX_DIR, index_name, "summary")
    os.makedirs(summary_path, exist_ok=True)

    # Reuse persisted summaries if they exist
    if os.path.exists(os.path.join(summary_path, "docstore.json")):
        logger.info("Loading existing DocumentSummaryIndex from disk...")
        storage_context = StorageContext.from_defaults(persist_dir=summary_path)
        return load_index_from_storage(storage_context)

    logger.info(f"Building DocumentSummaryIndex for {len(documents)} files...")
    start = time.time()

    storage_context = StorageContext.from_defaults()

    summary_index = DocumentSummaryIndex.from_documents(
        documents,
        storage_context=storage_context,
        show_progress=True,
        # Response synthesizer prompt is kept brief to stay fast on local LLM
        summary_query=(
            "Summarize what this code file does in 2-3 sentences. "
            "Focus on its purpose and key functions, not implementation details."
        ),
    )

    summary_index.storage_context.persist(persist_dir=summary_path)
    logger.info(f"DocumentSummaryIndex built and saved in {time.time() - start:.2f}s")
    return summary_index


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
    _, collection = _get_chroma_collection(index_name)
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage_context,
    )
    logger.info(f"Loaded VectorStoreIndex '{index_name}' from ChromaDB")
    return index