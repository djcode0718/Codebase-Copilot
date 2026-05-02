import os
import json
import pickle
import numpy as np
import re
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from app.config import INDEX_DIR
from app.utils.logger import get_logger
from app.llm.llm_client import generate_summary

logger = get_logger(__name__)


def extract_functions(content: str) -> List[str]:
    pattern = r'def\s+([a-zA-Z0-9_]+)\('
    return re.findall(pattern, content)


def build_file_map(file_paths: List[str], repo_path: str, index_name: str):
    file_map = []

    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            continue

        if not content.strip():
            continue

        # 🔹 preview (Approach 2)
        preview = " ".join(content[:300].split())

        # 🔹 functions
        functions = extract_functions(content)

        # 🔹 basic summary (fallback)
        # summary = preview

        snippet = "\n".join(content.splitlines()[:80])
        if should_use_llm(file_path, content):
            try:
                prompt = f"""
        Summarize this code file in 2-3 lines.
        Focus on what the file does, not implementation details.

        {snippet}
        """
                summary = generate_summary(prompt)
            except:
                summary = preview
        else:
            summary = preview

        file_map.append({
            "file": os.path.relpath(file_path, repo_path),
            "summary": summary,
            "preview": preview,
            "functions": functions
        })

    # 🔥 Create embeddings for summaries
    texts = [item["summary"] for item in file_map]

    vectorizer = TfidfVectorizer(max_features=256)
    embeddings = vectorizer.fit_transform(texts).toarray()

    # 🔹 Save everything
    base_path = os.path.join(INDEX_DIR, index_name)

    with open(base_path + "_file_map.json", "w") as f:
        json.dump(file_map, f, indent=2)

    np.save(base_path + "_file_map_embeddings.npy", embeddings)

    with open(base_path + "_file_map_vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)

    logger.info(f"File map built with {len(file_map)} files.")

    return file_map

def should_use_llm(file_path: str, content: str) -> bool:
    name = file_path.lower()
    return (
        "readme" in name or
        "main" in name or
        len(content) > 3000
    )

# HJ
# TODO: Implement summary caching
