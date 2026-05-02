import os
import json
import pickle
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.config import INDEX_DIR


def retrieve_relevant_files(query: str, index_name: str, top_k: int = 3):
    base_path = os.path.join(INDEX_DIR, index_name)

    with open(base_path + "_file_map.json") as f:
        file_map = json.load(f)

    embeddings = np.load(base_path + "_file_map_embeddings.npy")

    with open(base_path + "_file_map_vectorizer.pkl", "rb") as f:
        vectorizer = pickle.load(f)

    query_vec = vectorizer.transform([query]).toarray()

    similarities = cosine_similarity(query_vec, embeddings)[0]

    top_indices = np.argsort(similarities)[::-1][:top_k]

    return [file_map[i] for i in top_indices]