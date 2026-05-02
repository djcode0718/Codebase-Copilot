# from typing import List, Dict, Any, Tuple
# import numpy as np
# from sentence_transformers import SentenceTransformer
# from app.indexing.vector_store import VectorStore
# from app.config import EMBEDDING_MODEL
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# # Cache model so we don't reload it per query
# _model = None

# def _get_model() -> SentenceTransformer:
#     global _model
#     if _model is None:
#         logger.info(f"Loading embedding model for retrieval: {EMBEDDING_MODEL}")
#         _model = SentenceTransformer(EMBEDDING_MODEL)
#     return _model

# def retrieve_relevant_chunks(query: str, vector_store: VectorStore, top_k: int = 5) -> List[Dict[str, Any]]:
#     """
#     Converts query to embedding and retrieves top-k relevant chunks.
#     """
#     if not query.strip():
#         return []
        
#     model = _get_model()
#     query_embedding = model.encode(query)
    
#     # search vector store
#     results = vector_store.search(np.array([query_embedding]), top_k=top_k)
    
#     # We only return the metadata/chunk info, stripping the distance score for the prompt
#     retrieved_chunks = [item[0] for item in results]
    
#     logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query: '{query}'")
#     return retrieved_chunks


# from typing import List, Dict, Any
# import numpy as np
# from sklearn.metrics.pairwise import cosine_similarity
# from app.indexing.vector_store import VectorStore
# from app.utils.logger import get_logger

# logger = get_logger(__name__)

# def retrieve_relevant_chunks(query: str, vector_store: VectorStore, top_k: int = 5) -> List[Dict[str, Any]]:
#     """
#     Retrieve top-k relevant chunks using cosine similarity on TF-IDF embeddings.
#     """
#     if not query.strip():
#         return []

#     # Transform query using same vectorizer
#     query_vector = vector_store.vectorizer.transform([query]).toarray()

#     # Get stored embeddings
#     stored_embeddings = vector_store.embeddings

#     # Compute similarity
#     similarities = cosine_similarity(query_vector, stored_embeddings)[0]

#     threshold = 0.1

#     filtered_indices = [i for i, score in enumerate(similarities) if score > threshold]

#     # fallback if nothing passes threshold
#     if not filtered_indices:
#         filtered_indices = list(range(len(similarities)))

#     top_indices = sorted(
#         filtered_indices,
#         key=lambda i: similarities[i],
#         reverse=True
#     )[:top_k]

#     # # Get top-k indices
#     # top_indices = np.argsort(similarities)[::-1][:top_k]

#     # Retrieve chunks
#     retrieved_chunks = [vector_store.metadata[i] for i in top_indices]

#     logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query: '{query}'")
#     return retrieved_chunks

from typing import List, Dict, Any
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.indexing.vector_store import VectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)

def retrieve_relevant_chunks(query: str, vector_store: VectorStore, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve top-k relevant chunks using cosine similarity on TF-IDF embeddings.
    """
    if not query.strip():
        return []

    # Transform query using same vectorizer
    query_vector = vector_store.vectorizer.transform([query]).toarray()

    # Get stored embeddings
    stored_embeddings = vector_store.embeddings

    # Compute similarity
    similarities = cosine_similarity(query_vector, stored_embeddings)[0]

    # Get top-k indices
    top_indices = np.argsort(similarities)[::-1][:top_k]

    # Retrieve chunks
    retrieved_chunks = [vector_store.metadata[i] for i in top_indices]

    logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query: '{query}'")
    return retrieved_chunks