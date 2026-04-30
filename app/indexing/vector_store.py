# import os
# import json
# import faiss
# import numpy as np
# from typing import List, Dict, Any, Tuple
# from app.config import INDEX_DIR
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# class VectorStore:
#     def __init__(self, index_name: str = "default", dimension: int = 384):
#         """
#         Initialize the FAISS vector store.
#         `dimension` is based on the embedding model (e.g., all-MiniLM-L6-v2 is 384).
#         """
#         self.index_name = index_name
#         self.dimension = dimension
#         self.index_path = os.path.join(INDEX_DIR, f"{index_name}.faiss")
#         self.metadata_path = os.path.join(INDEX_DIR, f"{index_name}_metadata.json")
        
#         # We store metadata separately as required: (file, function, path, text)
#         self.metadata: List[Dict[str, Any]] = []
        
#         # Initialize FAISS index
#         self.index = faiss.IndexFlatL2(dimension)
        
#     def add_embeddings(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
#         """
#         Adds embeddings to FAISS and their corresponding metadata to our separate list.
#         """
#         if len(embeddings) != len(metadata_list):
#             raise ValueError("Number of embeddings and metadata items must match.")
            
#         if len(embeddings) == 0:
#             return
            
#         # Add to FAISS index
#         self.index.add(embeddings.astype('float32'))
        
#         # Store metadata
#         self.metadata.extend(metadata_list)
#         logger.info(f"Added {len(embeddings)} vectors to the store.")
        
#     def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
#         """
#         Searches the vector store and returns the top_k relevant metadata and distances.
#         """
#         if self.index.ntotal == 0:
#             return []
            
#         distances, indices = self.index.search(query_embedding.astype('float32'), top_k)
        
#         results = []
#         for i in range(len(indices[0])):
#             idx = indices[0][i]
#             if idx != -1 and idx < len(self.metadata):
#                 dist = float(distances[0][i])
#                 results.append((self.metadata[idx], dist))
                
#         return results
        
#     def save(self):
#         """Saves the FAISS index and the metadata JSON to disk."""
#         try:
#             faiss.write_index(self.index, self.index_path)
#             with open(self.metadata_path, 'w', encoding='utf-8') as f:
#                 json.dump(self.metadata, f, ensure_ascii=False, indent=2)
#             logger.info(f"Vector store '{self.index_name}' saved successfully.")
#         except Exception as e:
#             logger.error(f"Failed to save vector store: {e}")
#             raise
            
#     def load(self) -> bool:
#         """Loads the FAISS index and metadata from disk. Returns True if successful."""
#         if not os.path.exists(self.index_path) or not os.path.exists(self.metadata_path):
#             logger.info(f"No existing index found for '{self.index_name}'.")
#             return False
            
#         try:
#             self.index = faiss.read_index(self.index_path)
#             with open(self.metadata_path, 'r', encoding='utf-8') as f:
#                 self.metadata = json.load(f)
#             logger.info(f"Vector store '{self.index_name}' loaded successfully. Total vectors: {self.index.ntotal}")
#             return True
#         except Exception as e:
#             logger.error(f"Failed to load vector store: {e}")
#             return False

# def create_vector_store(index_name: str) -> VectorStore:
#     """Factory function to create a new VectorStore instance."""
#     return VectorStore(index_name)


import os
import json
import faiss
import numpy as np
import pickle
from typing import List, Dict, Any, Tuple
from app.config import INDEX_DIR
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    def __init__(self, index_name: str = "default", dimension: int = 384):
        self.index_name = index_name
        self.dimension = dimension

        self.index_path = os.path.join(INDEX_DIR, f"{index_name}.faiss")
        self.metadata_path = os.path.join(INDEX_DIR, f"{index_name}_metadata.json")
        self.embeddings_path = os.path.join(INDEX_DIR, f"{index_name}_embeddings.npy")
        self.vectorizer_path = os.path.join(INDEX_DIR, f"{index_name}_vectorizer.pkl")

        # Core storage
        self.metadata: List[Dict[str, Any]] = []
        self.embeddings: np.ndarray = None
        self.vectorizer = None

        # FAISS (optional)
        self.index = faiss.IndexFlatL2(dimension)

    def add_embeddings(self, embeddings: np.ndarray, metadata_list: List[Dict[str, Any]]):
        if len(embeddings) != len(metadata_list):
            raise ValueError("Embeddings and metadata must match in size.")

        if len(embeddings) == 0:
            return

        embeddings = embeddings.astype("float32")

        # Store embeddings
        if self.embeddings is None:
            self.embeddings = embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, embeddings])

        # Optional FAISS
        self.index.add(embeddings)

        # Store metadata
        self.metadata.extend(metadata_list)

        logger.info(f"Added {len(embeddings)} vectors to the store.")

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        if self.index.ntotal == 0:
            return []

        distances, indices = self.index.search(query_embedding.astype("float32"), top_k)

        results = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            if idx != -1 and idx < len(self.metadata):
                dist = float(distances[0][i])
                results.append((self.metadata[idx], dist))

        return results

    def save(self):
        try:
            # Save FAISS
            faiss.write_index(self.index, self.index_path)

            # Save metadata
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)

            # Save embeddings
            np.save(self.embeddings_path, self.embeddings)

            # ✅ Save vectorizer (CRITICAL FIX)
            if self.vectorizer is not None:
                with open(self.vectorizer_path, "wb") as f:
                    pickle.dump(self.vectorizer, f)

            logger.info(f"Vector store '{self.index_name}' saved successfully.")

        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
            raise

    def load(self) -> bool:
        try:
            if not os.path.exists(self.index_path):
                return False

            self.index = faiss.read_index(self.index_path)

            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

            if os.path.exists(self.embeddings_path):
                self.embeddings = np.load(self.embeddings_path)

            # ✅ Load vectorizer (CRITICAL FIX)
            if os.path.exists(self.vectorizer_path):
                with open(self.vectorizer_path, "rb") as f:
                    self.vectorizer = pickle.load(f)

            logger.info(f"Loaded vector store '{self.index_name}' successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False


def create_vector_store(index_name: str) -> VectorStore:
    return VectorStore(index_name)