import os
import json
import subprocess
from typing import List, Dict
from llama_index.core import Document
from app.config import INDEX_DIR, INDEX_GIT_HISTORY, GIT_HISTORY_MAX_COMMITS_PER_FILE
from app.utils.logger import get_logger

logger = get_logger(__name__)


def load_git_history_for_file(file_path: str, repo_path: str) -> List[Document]:
    """Get git history chunks for a single file."""
    if not INDEX_GIT_HISTORY:
        return []

    try:
        rel_path = os.path.relpath(file_path, repo_path)
    except Exception:
        rel_path = file_path

    max_commits = GIT_HISTORY_MAX_COMMITS_PER_FILE

    try:
        cmd = ["git", "log", "--follow", "-p", "-m", "-n", str(max_commits), "--", rel_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        if result.returncode != 0:
            # Fallback without --follow in case of shallow clone or git version issue
            cmd_fallback = ["git", "log", "-p", "-m", "-n", str(max_commits), "--", rel_path]
            result = subprocess.run(
                cmd_fallback,
                capture_output=True,
                text=True,
                cwd=repo_path,
            )
            if result.returncode != 0:
                return []

        git_log_output = result.stdout
        if not git_log_output or not git_log_output.strip():
            return []

        from app.parsing.chunk_utils import chunk_text
        chunks = chunk_text(git_log_output, max_chunk_size=1200, overlap=100)

        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                text=chunk,
                metadata={
                    "file_name": os.path.basename(file_path),
                    "path": rel_path,
                    "doc_type": "git_history",
                    "chunk_index": i
                },
                excluded_embed_metadata_keys=["doc_type", "chunk_index"]
            )
            documents.append(doc)
        return documents
    except Exception as e:
        logger.warning(f"Failed to get git history for {rel_path}: {e}")
        return []


def save_git_history_dict(history_dict: Dict[str, List[Document]], index_name: str):
    """Save git history dict as JSON atomically."""
    history_dir = os.path.join(INDEX_DIR, index_name)
    os.makedirs(history_dir, exist_ok=True)
    history_path = os.path.join(history_dir, "git_history.json")
    tmp_path = os.path.join(history_dir, "git_history.json.tmp")

    data = {}
    for file_path, docs in history_dict.items():
        data[file_path] = [
            {
                "text": doc.text,
                "metadata": doc.metadata
            }
            for doc in docs
        ]
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, history_path)
    except Exception as e:
        logger.warning(f"Failed to save git history: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def load_persisted_git_history(index_name: str) -> List[Document]:
    """Load all persisted git history documents as a flat list."""
    history_dir = os.path.join(INDEX_DIR, index_name)
    history_path = os.path.join(history_dir, "git_history.json")
    tmp_path = os.path.join(history_dir, "git_history.json.tmp")

    if not os.path.exists(history_path) and os.path.exists(tmp_path):
        try:
            os.replace(tmp_path, history_path)
        except Exception:
            pass

    if not os.path.exists(history_path):
        return []

    try:
        with open(history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        docs = []
        for file_path, items in data.items():
            for item in items:
                docs.append(Document(
                    text=item["text"],
                    metadata=item["metadata"],
                    excluded_embed_metadata_keys=["doc_type", "chunk_index"]
                ))
        return docs
    except Exception as e:
        logger.warning(f"Failed to load persisted git history: {e}")
        return []


def build_and_save_full_git_history(valid_files: List[str], repo_path: str, index_name: str) -> List[Document]:
    """Build git history for all valid files and save to disk."""
    if not INDEX_GIT_HISTORY:
        return []

    # Quick verification that repo_path is inside a valid git repository
    try:
        chk = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if chk.returncode != 0:
            logger.info(f"Directory {repo_path} is not a git repository. Skipping git history ingestion.")
            return []
    except Exception as e:
        logger.warning(f"Git check failed for {repo_path}: {e}")
        return []

    history_dict = {}
    all_docs = []
    for fp in valid_files:
        docs = load_git_history_for_file(fp, repo_path)
        if docs:
            history_dict[fp] = docs
            all_docs.extend(docs)
    save_git_history_dict(history_dict, index_name)
    return all_docs
