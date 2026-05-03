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

from typing import List, Dict, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from app.indexing.vector_store import VectorStore
from app.utils.logger import get_logger
import time

logger = get_logger(__name__)


def build_index(chunks: List[Dict[str, Any]], index_name: str = "default") -> VectorStore:
    """
    Converts parsed code chunks into TF-IDF embeddings and saves them
    to the vector store. This will be replaced by nomic-embed-text
    dense embeddings in the LlamaIndex migration.
    """

    if not chunks:
        logger.warning("No chunks provided to build_index.")
        return None

    # 🔹 Extract texts
    texts = [chunk["text"] for chunk in chunks]

    logger.info(f"Building TF-IDF index for {len(texts)} chunks...")

    # 🔹 Fit vectorizer
    vectorizer = TfidfVectorizer(
        max_features=1000,
        stop_words="english",
        lowercase=True
    )

    start_time = time.time()
    embeddings = vectorizer.fit_transform(texts).toarray()
    logger.info(f"Vectorization completed in {time.time() - start_time:.2f}s")

    dimension = embeddings.shape[1]

    # 🔹 Initialize and populate vector store
    vector_store = VectorStore(index_name, dimension=dimension)
    vector_store.vectorizer = vectorizer
    vector_store.add_embeddings(np.array(embeddings), chunks)

    # 🔹 Persist to disk
    vector_store.save()

    logger.info(f"Index '{index_name}' built and saved — {len(chunks)} chunks, dimension={dimension}.")

    return vector_store