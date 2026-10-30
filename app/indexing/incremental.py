import os
import json
import hashlib
from typing import List, Dict, Set, Tuple
from llama_index.core import Document
from app.config import INDEX_DIR
from app.ingestion.file_filter import filter_files
from app.parsing.code_parser import load_documents, parse_documents
from app.indexing.index_builder import load_vector_index, _get_chroma_collection
from app.ingestion.git_history import load_git_history_for_file
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_file_hash(file_path: str) -> str:
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.warning(f"Failed to calculate hash for {file_path}: {e}")
        return ""


def load_manifest(index_name: str) -> Dict[str, Dict]:
    """Load manifest.json for a given index with fallback recovery."""
    manifest_dir = os.path.join(INDEX_DIR, index_name)
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    tmp_path = os.path.join(manifest_dir, "manifest.json.tmp")

    if not os.path.exists(manifest_path) and os.path.exists(tmp_path):
        try:
            os.replace(tmp_path, manifest_path)
        except Exception:
            pass

    if not os.path.exists(manifest_path):
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load manifest: {e}")
        if os.path.exists(tmp_path):
            try:
                with open(tmp_path, "r", encoding="utf-8") as tf:
                    return json.load(tf)
            except Exception:
                pass
        return {}


def save_manifest(index_name: str, manifest: Dict[str, Dict]):
    """Save manifest.json for a given index atomically."""
    manifest_dir = os.path.join(INDEX_DIR, index_name)
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    tmp_path = os.path.join(manifest_dir, "manifest.json.tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(tmp_path, manifest_path)
    except Exception as e:
        logger.warning(f"Failed to save manifest: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def build_initial_manifest(nodes: List, repo_path: str, index_name: str):
    """Build and save initial manifest.json during full build."""
    manifest = {}
    for node in nodes:
        rel_path = node.metadata.get("path")
        if not rel_path or rel_path == "_codebase_context":
            continue
        abs_path = os.path.join(repo_path, rel_path)
        if os.path.exists(abs_path):
            file_hash = get_file_hash(abs_path)
            manifest.setdefault(rel_path, {"hash": file_hash, "chunk_ids": []})["chunk_ids"].append(node.node_id)
    save_manifest(index_name, manifest)


def run_incremental_indexing(repo_path: str, index_name: str) -> bool:
    """
    Run incremental (diff-based) reindexing.
    Returns True if update occurred, False otherwise (indicating full build required).
    """
    manifest = load_manifest(index_name)
    if not manifest:
        logger.info(f"No manifest found for {index_name}. Incremental re-indexing fallback to full build.")
        return False
        
    logger.info(f"Running incremental re-indexing for {index_name}")
    valid_files = filter_files(repo_path)
    
    current_files = {os.path.abspath(fp): os.path.relpath(fp, repo_path) for fp in valid_files}
    manifest_files = {os.path.abspath(os.path.join(repo_path, fp)): fp for fp in manifest.keys()}
    
    added_abs = set(current_files.keys()) - set(manifest_files.keys())
    deleted_abs = set(manifest_files.keys()) - set(current_files.keys())
    
    modified_abs = set()
    for abs_path in set(current_files.keys()) & set(manifest_files.keys()):
        rel_path = current_files[abs_path]
        current_hash = get_file_hash(abs_path)
        manifest_hash = manifest[rel_path].get("hash", "")
        if current_hash != manifest_hash:
            modified_abs.add(abs_path)
            
    if not added_abs and not deleted_abs and not modified_abs:
        logger.info("No files added, deleted, or modified. Index is up to date.")
        return True
        
    index = load_vector_index(index_name)
    _, collection = _get_chroma_collection(index_name)
    
    # Load existing git history dictionary
    git_history_path = os.path.join(INDEX_DIR, index_name, "git_history.json")
    git_history_dict = {}
    if os.path.exists(git_history_path):
        try:
            with open(git_history_path, "r", encoding="utf-8") as f:
                git_data = json.load(f)
            for fp, items in git_data.items():
                git_history_dict[fp] = [
                    Document(
                        text=item["text"],
                        metadata=item["metadata"],
                        excluded_embed_metadata_keys=["doc_type", "chunk_index"]
                    )
                    for item in items
                ]
        except Exception as ge:
            logger.warning(f"Failed to load git history: {ge}")
            
    # Process deletions
    node_ids_to_delete = []
    for abs_path in deleted_abs | modified_abs:
        rel_path = None
        for k in manifest.keys():
            if os.path.abspath(os.path.join(repo_path, k)) == abs_path:
                rel_path = k
                break
        if rel_path and rel_path in manifest:
            chunk_ids = manifest[rel_path].get("chunk_ids", [])
            node_ids_to_delete.extend(chunk_ids)
            del manifest[rel_path]
            git_history_dict.pop(rel_path, None)

    if node_ids_to_delete:
        logger.info(f"Deleting {len(node_ids_to_delete)} old nodes from Chroma and docstore")
        try:
            collection.delete(ids=node_ids_to_delete)
        except Exception as e:
            logger.warning(f"Failed to delete old nodes from Chroma: {e}")
        try:
            if hasattr(index, "docstore"):
                for nid in node_ids_to_delete:
                    index.docstore.delete_document(nid, raise_error=False)
        except Exception as e:
            logger.warning(f"Failed to delete old nodes from docstore: {e}")
            
    # Process additions / modifications
    for abs_path in added_abs | modified_abs:
        rel_path = current_files[abs_path]
        logger.info(f"Re-indexing file: {rel_path}")
        
        try:
            docs = load_documents([abs_path], repo_path)
            nodes = parse_documents(docs)
            if nodes:
                index.insert_nodes(nodes)
                chunk_ids = [node.node_id for node in nodes]
                manifest[rel_path] = {
                    "hash": get_file_hash(abs_path),
                    "chunk_ids": chunk_ids
                }
        except Exception as e:
            logger.warning(f"Failed to re-index {rel_path}: {e}")
            
        try:
            git_docs = load_git_history_for_file(abs_path, repo_path)
            if git_docs:
                git_history_dict[rel_path] = git_docs
        except Exception as ge:
            logger.warning(f"Failed to update git history for {rel_path}: {ge}")

    # Save manifest
    save_manifest(index_name, manifest)
    
    # Save updated git history
    from app.ingestion.git_history import save_git_history_dict
    save_git_history_dict(git_history_dict, index_name)
    
    logger.info("Incremental re-indexing complete.")
    return True
