# import os
# import json
# import pickle
# import numpy as np
# import re
# from typing import List, Dict, Any
# from sklearn.feature_extraction.text import TfidfVectorizer
# from app.config import INDEX_DIR
# from app.utils.logger import get_logger
# from app.llm.llm_client import generate_summary
# from tqdm import tqdm
# import time

# logger = get_logger(__name__)


# def extract_functions(content: str) -> List[str]:
#     pattern = r'def\s+([a-zA-Z0-9_]+)\('
#     return re.findall(pattern, content)


# def build_file_map(file_paths: List[str], repo_path: str, index_name: str):
#     file_map = []

#     start_time = time.time()

#     for file_path in tqdm(file_paths, desc="Building file map"):    
#         logger.info(f"Processing file for summary: {file_path}")

#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#         except:
#             continue

#         if not content.strip():
#             continue

#         # 🔹 preview (Approach 2)
#         preview = " ".join(content[:300].split())

#         # 🔹 functions
#         functions = extract_functions(content)

#         # 🔹 basic summary (fallback)
#         # summary = preview

#         snippet = "\n".join(content.splitlines()[:80])
#         if should_use_llm(file_path, content):
#             try:
#                 prompt = f"""
#         Summarize this code file in 2-3 lines.
#         Focus on what the file does, not implementation details.

#         {snippet}
#         """
#                 llm_start = time.time()

#                 summary = generate_summary(prompt)
#                 logger.info(f"Summary generated in {time.time() - llm_start:.2f}s for {file_path}")
#             except:
#                 summary = preview
#         else:
#             summary = preview

#         file_map.append({
#             "file": os.path.relpath(file_path, repo_path),
#             "summary": summary,
#             "preview": preview,
#             "functions": functions
#         })

#     # 🔥 Create embeddings for summaries
#     texts = [item["summary"] for item in file_map]

#     vectorizer = TfidfVectorizer(max_features=256)
#     embeddings = vectorizer.fit_transform(texts).toarray()

#     # 🔹 Save everything
#     base_path = os.path.join(INDEX_DIR, index_name)

#     with open(base_path + "_file_map.json", "w") as f:
#         json.dump(file_map, f, indent=2)

#     np.save(base_path + "_file_map_embeddings.npy", embeddings)

#     with open(base_path + "_file_map_vectorizer.pkl", "wb") as f:
#         pickle.dump(vectorizer, f)

#     logger.info(f"File map built with {len(file_map)} files.")

#     logger.info(f"File map build time: {time.time() - start_time:.2f}s")
#     return file_map

# def should_use_llm(file_path: str, content: str) -> bool:
#     name = file_path.lower()
#     return (
#         "readme" in name or
#         "main" in name or
#         len(content) > 3000
#     )


# import os
# import json
# import pickle
# import numpy as np
# import re
# from typing import List, Dict, Any
# from sklearn.feature_extraction.text import TfidfVectorizer
# from app.config import INDEX_DIR
# from app.utils.logger import get_logger
# from app.llm.llm_client import generate_summary
# from tqdm import tqdm
# import time

# logger = get_logger(__name__)

# # 🔥 CONFIG (tune this if needed)
# MAX_FILES_FOR_FILE_MAP = 40


# def extract_functions(content: str) -> List[str]:
#     pattern = r'def\s+([a-zA-Z0-9_]+)\('
#     return re.findall(pattern, content)


# def prioritize_files(file_paths: List[str]) -> List[str]:
#     """
#     Prioritize important files (README, main, smaller paths first)
#     """
#     return sorted(file_paths, key=lambda x: (
#         "readme" not in x.lower(),
#         "main" not in x.lower(),
#         len(x)
#     ))


# def build_file_map(file_paths: List[str], repo_path: str, index_name: str):
#     file_map = []
#     start_time = time.time()

#     # 🔥 Prioritize files before processing
#     file_paths = prioritize_files(file_paths)

#     logger.info(f"Total files received: {len(file_paths)}")

#     for file_path in tqdm(file_paths, desc="Building file map"):

#         # 🔒 LIMIT CONTROL
#         if len(file_map) >= MAX_FILES_FOR_FILE_MAP:
#             logger.warning(f"Reached file map limit ({MAX_FILES_FOR_FILE_MAP}) → stopping early")
#             break

#         logger.info(f"Processing file: {file_path}")

#         try:
#             with open(file_path, 'r', encoding='utf-8') as f:
#                 content = f.read()
#         except Exception as e:
#             logger.warning(f"Skipped file (read error): {file_path} → {e}")
#             continue

#         if not content.strip():
#             logger.warning(f"Skipped empty file: {file_path}")
#             continue

#         # 🔒 Skip very small files (low value)
#         if len(content) < 50:
#             logger.warning(f"Skipped tiny file: {file_path}")
#             continue

#         # 🔹 preview
#         preview = " ".join(content[:300].split())

#         # 🔹 functions
#         functions = extract_functions(content)

#         # 🔹 LLM summary decision
#         snippet = "\n".join(content.splitlines()[:80])

#         if should_use_llm(file_path, content):
#             try:
#                 prompt = f"""
# Summarize this code file in 2-3 lines.
# Focus on what the file does, not implementation details.

# {snippet}
# """
#                 llm_start = time.time()

#                 summary = generate_summary(prompt)

#                 logger.info(
#                     f"Summary generated in {time.time() - llm_start:.2f}s for {file_path}"
#                 )

#             except Exception as e:
#                 logger.warning(f"LLM summary failed for {file_path} → {e}")
#                 summary = preview
#         else:
#             summary = preview

#         file_map.append({
#             "file": os.path.relpath(file_path, repo_path),
#             "summary": summary,
#             "preview": preview,
#             "functions": functions
#         })

#     # 🔥 Safety: ensure non-empty
#     if not file_map:
#         logger.error("File map is empty. No valid files processed.")
#         return []

#     # 🔥 Create embeddings
#     texts = [item["summary"] for item in file_map]

#     vectorizer = TfidfVectorizer(
#         max_features=256,
#         stop_words="english",
#         lowercase=True
#     )

#     embeddings = vectorizer.fit_transform(texts).toarray()

#     # 🔹 Save everything
#     base_path = os.path.join(INDEX_DIR, index_name)

#     with open(base_path + "_file_map.json", "w") as f:
#         json.dump(file_map, f, indent=2)

#     np.save(base_path + "_file_map_embeddings.npy", embeddings)

#     with open(base_path + "_file_map_vectorizer.pkl", "wb") as f:
#         pickle.dump(vectorizer, f)

#     logger.info(f"File map built with {len(file_map)} files.")
#     logger.info(f"File map build time: {time.time() - start_time:.2f}s")

#     return file_map


# def should_use_llm(file_path: str, content: str) -> bool:
#     name = file_path.lower()
#     return (
#         "readme" in name or
#         "main" in name or
#         len(content) > 3000
#     )

import os
import json
import pickle
import re
import time
from typing import List, Dict, Any
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from tqdm import tqdm

from app.config import INDEX_DIR
from app.utils.logger import get_logger
from app.llm.llm_client import generate_summary

logger = get_logger(__name__)

MAX_FILES_FOR_FILE_MAP = 40


def extract_functions(content: str) -> List[str]:
    """Extract top-level function names from Python source."""
    pattern = r'def\s+([a-zA-Z0-9_]+)\('
    return re.findall(pattern, content)


def prioritize_files(file_paths: List[str]) -> List[str]:
    """
    Sort files so README, main, and shorter paths come first.
    These are most likely to contain high-signal summaries.
    """
    return sorted(file_paths, key=lambda x: (
        "readme" not in x.lower(),
        "main" not in x.lower(),
        len(x)
    ))


def should_use_llm(file_path: str, content: str) -> bool:
    """
    Use LLM summarization only for high-value files.
    Keeps indexing fast on local Ollama.
    """
    name = file_path.lower()
    return (
        "readme" in name or
        "main" in name or
        len(content) > 3000
    )


def build_file_map(file_paths: List[str], repo_path: str, index_name: str) -> List[Dict[str, Any]]:
    """
    Build a file-level summary map for coarse retrieval.
    Each file gets: summary text, preview, and extracted function names.
    TF-IDF embeddings of summaries are saved for fast file-level lookup.
    """
    file_map = []
    start_time = time.time()

    file_paths = prioritize_files(file_paths)
    logger.info(f"Building file map for {len(file_paths)} files (cap: {MAX_FILES_FOR_FILE_MAP})")

    for file_path in tqdm(file_paths, desc="Building file map"):

        if len(file_map) >= MAX_FILES_FOR_FILE_MAP:
            logger.warning(f"Reached file map limit ({MAX_FILES_FOR_FILE_MAP}) — stopping early")
            break

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Skipped (read error): {file_path} — {e}")
            continue

        if not content.strip() or len(content) < 50:
            logger.warning(f"Skipped (empty or tiny): {file_path}")
            continue

        preview = " ".join(content[:300].split())
        functions = extract_functions(content)
        snippet = "\n".join(content.splitlines()[:80])

        if should_use_llm(file_path, content):
            try:
                prompt = (
                    "Summarize this code file in 2-3 lines. "
                    "Focus on what the file does, not implementation details.\n\n"
                    f"{snippet}"
                )
                llm_start = time.time()
                summary = generate_summary(prompt)
                logger.info(f"LLM summary in {time.time() - llm_start:.2f}s — {file_path}")
            except Exception as e:
                logger.warning(f"LLM summary failed for {file_path} — {e}")
                summary = preview
        else:
            summary = preview

        # Use posix paths for cross-platform consistency
        relative_path = Path(os.path.relpath(file_path, repo_path)).as_posix()

        file_map.append({
            "file": relative_path,
            "summary": summary,
            "preview": preview,
            "functions": functions
        })

    if not file_map:
        logger.error("File map is empty — no valid files were processed.")
        return []

    # 🔹 Build TF-IDF embeddings over summaries
    texts = [item["summary"] for item in file_map]
    vectorizer = TfidfVectorizer(
        max_features=256,
        stop_words="english",
        lowercase=True
    )
    embeddings = vectorizer.fit_transform(texts).toarray()

    # 🔹 Persist to disk
    base_path = os.path.join(INDEX_DIR, index_name)

    with open(base_path + "_file_map.json", "w") as f:
        json.dump(file_map, f, indent=2)

    np.save(base_path + "_file_map_embeddings.npy", embeddings)

    with open(base_path + "_file_map_vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)

    logger.info(f"File map saved — {len(file_map)} files in {time.time() - start_time:.2f}s")

    return file_map


# # # HJ
# # # TODO: Implement summary caching


