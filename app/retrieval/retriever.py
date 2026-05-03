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
#     query_vector = np.nan_to_num(query_vector)

#     # Get stored embeddings
#     stored_embeddings = vector_store.embeddings
#     stored_embeddings = np.nan_to_num(stored_embeddings)

#     # Compute similarity
#     # similarities = cosine_similarity(query_vector, stored_embeddings)[0]

#     from sklearn.metrics.pairwise import cosine_similarity

#     # Convert safely
#     query_vector = vector_store.vectorizer.transform([query]).toarray()

#     # 🔒 FIX 1: Replace NaN / inf
#     query_vector = np.nan_to_num(query_vector)

#     stored_embeddings = np.nan_to_num(vector_store.embeddings)

#     # 🔒 FIX 2: Handle zero vector query
#     if np.linalg.norm(query_vector) == 0:
#         logger.warning("Query vector is zero. Returning top chunks without similarity.")
#         return vector_store.metadata[:top_k]

#     # 🔒 FIX 3: Compute similarity safely
#     similarities = cosine_similarity(query_vector, stored_embeddings)[0]

#     # 🔒 FIX 4: Clean output
#     similarities = np.nan_to_num(similarities)

#     # 🔒 FIX 5: Handle all-zero similarity
#     if np.all(similarities == 0):
#         logger.warning("All similarities are zero. Returning fallback chunks.")
#         return vector_store.metadata[:top_k]

#     # 🔒 Sort normally
#     top_indices = similarities.argsort()[-top_k:][::-1]

#     return [vector_store.metadata[i] for i in top_indices]

#     # Get top-k indices
#     top_indices = np.argsort(similarities)[::-1][:top_k]

#     # Retrieve chunks
#     retrieved_chunks = [vector_store.metadata[i] for i in top_indices]

#     logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query: '{query}'")
#     return retrieved_chunks

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
    - TF-IDF similarity
    - File-level boosting
    - Keyword overlap
    """

    if not query.strip():
        return []

    # 🔹 Query vector
    query_vec = vector_store.vectorizer.transform([query]).toarray()
    query_vec = np.nan_to_num(query_vec)

    embeddings = np.nan_to_num(vector_store.embeddings)

    # 🔒 Handle zero query
    if np.linalg.norm(query_vec) == 0:
        logger.warning("Query vector is zero → fallback")
        return vector_store.metadata[:top_k]

    # 🔹 Normalize
    query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    emb_norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (emb_norms + 1e-10)

    similarities = np.dot(embeddings, query_vec.T).flatten()
    similarities = np.nan_to_num(similarities)

    relevant_files_set = set(relevant_files)

    scored_chunks = []

    for i, chunk in enumerate(vector_store.metadata):
        score = similarities[i]

        file_path = chunk["metadata"]["path"]

        # 🔥 File boost
        if file_path in relevant_files_set:
            score += 0.4

        # 🔥 Keyword overlap
        text = chunk["text"].lower()
        if any(word in text for word in query.lower().split()):
            score += 0.1

        chunk_copy = chunk.copy()
        chunk_copy["score"] = float(score)

        scored_chunks.append(chunk_copy)

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)

    logger.info(f"Hybrid retrieved {len(scored_chunks)} chunks")

    return scored_chunks[:top_k]