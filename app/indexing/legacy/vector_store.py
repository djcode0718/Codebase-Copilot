"""
LEGACY: This file implements the old TF-IDF vector store and is no longer used in production.
It has been replaced by VectorStoreIndex (ChromaDB + nomic-embed-text) and DocumentSummaryIndex.
"""
import os
import json
import numpy as np
import pickle
from typing import List, Dict, Any
from app.config import INDEX_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    def __init__(self, index_name: str = "default", dimension: int = 384):
        self.index_name = index_name
        self.dimension = dimension

        self.metadata_path = os.path.join(INDEX_DIR, f"{index_name}_metadata.json")
        self.embeddings_path = os.path.join(INDEX_DIR, f"{index_name}_embeddings.npy")
        self.vectorizer_path = os.path.join(INDEX_DIR, f"{index_name}_vectorizer.pkl")

        self.metadata: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = None
        self.vectorizer = None

    def add_embeddings(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
        if len(embeddings) != len(metadata_list):
            raise ValueError("Embeddings and metadata must match in size.")

        if len(embeddings) == 0:
            return

        embeddings = embeddings.astype("float32")

        if self.embeddings is None:
            self.embeddings = embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])

        self.metadata.extend(metadata_list)

        logger.info(f"Added {len(embeddings)} vectors to the store.")

    def save(self):
        try:
            os.makedirs(INDEX_DIR, exist_ok=True)

            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)

            if self.embeddings is not None:
                np.save(self.embeddings_path, self.embeddings)

            if self.vectorizer is not None:
                with open(self.vectorizer_path, "wb") as f:
                    pickle.dump(self.vectorizer, f)

            logger.info(f"Vector store '{self.index_name}' saved successfully.")

        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            raise

    def load(self) -> bool:
        try:
            if not os.path.exists(self.metadata_path):
                logger.warning(f"No existing index found for '{self.index_name}'.")
                return False

            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

            if os.path.exists(self.embeddings_path):
                self.embeddings = np.load(self.embeddings_path)

            if os.path.exists(self.vectorizer_path):
                with open(self.vectorizer_path, "rb") as f:
                    self.vectorizer = pickle.load(f)

            logger.info(f"Loaded vector store '{self.index_name}' — {len(self.metadata)} chunks.")
            return True

        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False


def create_vector_store(index_name: str) -> VectorStore:
    return VectorStore(index_name)