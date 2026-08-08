"""
LEGACY: This file implements the old file map retriever and is no longer used in production.
It has been replaced by VectorStoreIndex (ChromaDB + nomic-embed-text) and DocumentSummaryIndex.
"""
import os
import json
import pickle
import numpy as np
from app.config import INDEX_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


def retrieve_relevant_files(query: str, index_name: str, top_k: int = 3):
    base_path = os.path.join(INDEX_DIR, index_name)

    # 🔹 Load file map
    with open(base_path + "_file_map.json") as f:
        file_map = json.load(f)

    # 🔹 Load embeddings
    embeddings = np.load(base_path + "_file_map_embeddings.npy")

    # 🔹 Load vectorizer
    with open(base_path + "_file_map_vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)

    # 🔹 Transform query
    query_vec = vectorizer.transform([query]).toarray()

    # 🔹 Clean NaN / inf
    query_vec = np.nan_to_num(query_vec)
    embeddings = np.nan_to_num(embeddings)

    # 🔒 Handle zero query vector
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        logger.warning("Query vector is zero → returning default files")
        return file_map[:top_k]

    # 🔹 Normalize query
    query_vec = query_vec / (query_norm + 1e-10)

    # 🔹 Normalize embeddings (row-wise)
    emb_norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (emb_norms + 1e-10)

    # 🔥 SAFE cosine similarity (dot product after normalization)
    similarities = np.dot(embeddings, query_vec.T).flatten()

    # 🔹 Clean again
    similarities = np.nan_to_num(similarities)

    # 🔒 All zero fallback
    if np.all(similarities == 0):
        logger.warning("All similarities zero → fallback")
        return file_map[:top_k]

    # 🔹 Get top results
    top_indices = np.argsort(similarities)[::-1][:top_k]

    # 🔹 Logging
    logger.info(f"Top {top_k} files selected for query: {query}")
    for i in top_indices:
        logger.info(f"Selected file: {file_map[i]['file']}")

    return [file_map[i] for i in top_indices]