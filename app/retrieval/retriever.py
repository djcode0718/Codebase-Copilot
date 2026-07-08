from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from app.indexing.vector_store import VectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


def retrieve_relevant_chunks(
    query: str,
    vector_store: VectorStore,
    relevant_files: List[str],
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    HYBRID RETRIEVAL:
    - TF-IDF cosine similarity (semantic approximation)
    - File-level score boosting
    - Keyword overlap boost
    """

    if not query.strip():
        return []

    # 🔹 Query vector
    query_vec = vector_store.vectorizer.transform([query]).toarray()
    query_vec = np.nan_to_num(query_vec)

    embeddings = np.nan_to_num(vector_store.embeddings)

    # 🔒 Handle zero query vector
    if np.linalg.norm(query_vec) == 0:
        logger.warning("Query vector is zero → fallback to top chunks")
        return vector_store.metadata[:top_k]

    # 🔹 Normalize both for cosine similarity
    query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    emb_norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (emb_norms + 1e-10)

    similarities = np.dot(embeddings, query_vec.T).flatten()
    similarities = np.nan_to_num(similarities)

    # 🔹 Normalize relevant file paths for reliable comparison
    relevant_files_set = {Path(f).as_posix() for f in relevant_files}

    scored_chunks = []

    for i, chunk in enumerate(vector_store.metadata):
        score = float(similarities[i])

        # 🔹 Normalize chunk path the same way
        chunk_path = Path(chunk["metadata"]["path"]).as_posix()

        # 🔥 File-level boost — only fires if paths match correctly
        if chunk_path in relevant_files_set:
            score += 0.4

        # 🔥 Keyword overlap boost
        text = chunk["text"].lower()
        query_words = query.lower().split()
        if any(word in text for word in query_words):
            score += 0.1

        chunk_copy = chunk.copy()
        chunk_copy["score"] = score
        scored_chunks.append(chunk_copy)

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"Hybrid retrieval complete — top {top_k} chunks selected from {len(scored_chunks)} total")

    return scored_chunks[:top_k]