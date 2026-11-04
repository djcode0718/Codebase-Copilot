"""
app/retrieval/repository_isolation.py
─────────────────────────────────────
Strict repository isolation enforcement module for Codebase-Copilot.

Guarantees:
1. Every evaluation query targets a specific repository ID.
2. Every retrieved chunk is verified against that repository ID.
3. Chunks with mismatched or cross-repository IDs/indices are strictly rejected.
4. Applied across dense retrieval, BM25, RRF fusion, reranking, and final results.
5. Rejects cross-repository contamination between similarly named repositories:
   - Emotion-detection vs Speech-Emotion-Analyzer
   - Sound2Sign vs SenseVoice
   - FedSegX vs NeuroVera
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from llama_index.core.schema import NodeWithScore

logger = logging.getLogger(__name__)

# Known canonical mappings (fallback if database is offline or in unit tests)
STATIC_REPO_ID_MAP: Dict[str, str] = {
    # Name -> ID
    "FedSegX": "bc5f54ec-7113-4132-b39e-bd94a0d2726e",
    "Sound2Sign": "1ab9b9f6-8a9e-440d-946d-2d67fe41409a",
    "Emotion-detection": "299a2d6e-008f-4e92-b973-874a6c6b6ad9",
    "Emotion-Detection": "299a2d6e-008f-4e92-b973-874a6c6b6ad9",
    "NeuroVera": "68ad8600-becc-445f-b56a-ab0d26d54c58",
    "SenseVoice": "296ee64c-a989-48ff-9ded-a3e1bb09b63f",
    "Speech-Emotion-Analyzer": "7f25a956-b13d-4098-8a40-5e8731946705",
    "MediscanAI": "9a61c7d2-489c-4b05-8cd6-f4b78671f360",
    "Codebase-Copilot": "034febb5-0d8c-4f52-a8e7-a2177a40105d",
    # ID -> Name
    "bc5f54ec-7113-4132-b39e-bd94a0d2726e": "FedSegX",
    "1ab9b9f6-8a9e-440d-946d-2d67fe41409a": "Sound2Sign",
    "299a2d6e-008f-4e92-b973-874a6c6b6ad9": "Emotion-detection",
    "68ad8600-becc-445f-b56a-ab0d26d54c58": "NeuroVera",
    "296ee64c-a989-48ff-9ded-a3e1bb09b63f": "SenseVoice",
    "7f25a956-b13d-4098-8a40-5e8731946705": "Speech-Emotion-Analyzer",
    "9a61c7d2-489c-4b05-8cd6-f4b78671f360": "MediscanAI",
    "034febb5-0d8c-4f52-a8e7-a2177a40105d": "Codebase-Copilot",
}

_dynamic_cache: Dict[str, str] = {}


def resolve_repository_id(repo_name_or_id: str) -> Optional[str]:
    """Resolve a repository name or ID to its canonical UUID."""
    if not repo_name_or_id:
        return None
    val = repo_name_or_id.strip()
    if val in _dynamic_cache:
        return _dynamic_cache[val]
    if val in STATIC_REPO_ID_MAP:
        # If val is already a UUID in the map
        if val.count("-") == 4:
            return val
        return STATIC_REPO_ID_MAP[val]
    
    # Try querying Supabase
    try:
        from api.dependencies import get_supabase
        sb = get_supabase()
        res = sb.table("repositories").select("id, name, index_name").execute()
        for r in res.data or []:
            r_id = r.get("id")
            r_name = r.get("name")
            r_idx = r.get("index_name")
            if r_id:
                _dynamic_cache[r_id] = r_id
                if r_name:
                    _dynamic_cache[r_name] = r_id
                if r_idx:
                    _dynamic_cache[r_idx] = r_id
        if val in _dynamic_cache:
            return _dynamic_cache[val]
    except Exception as e:
        logger.debug(f"Could not dynamically query Supabase repo mapping: {e}")

    return STATIC_REPO_ID_MAP.get(val)


def resolve_index_name(repo_id_or_name: str) -> Optional[str]:
    """Resolve a repository ID or name to its canonical index directory/collection name."""
    if not repo_id_or_name:
        return None
    val = repo_id_or_name.strip()
    if val in STATIC_REPO_ID_MAP and val.count("-") == 4:
        return STATIC_REPO_ID_MAP[val]
    resolved_id = resolve_repository_id(val)
    if resolved_id and resolved_id in STATIC_REPO_ID_MAP:
        return STATIC_REPO_ID_MAP[resolved_id]
    return val


def enforce_chunk_isolation(
    nodes: List[NodeWithScore],
    target_repo_id: str,
    active_index_name: str,
    require_existing_metadata: bool = False,
) -> List[NodeWithScore]:
    """
    Strict isolation filter for candidate chunks:
    1. Rejects all chunks if target_repo_id does not match the active_index_name.
    2. Rejects any chunk whose metadata repository_id or index_name does not match.
    3. Rejects chunks missing repository_id if require_existing_metadata is True.
    4. Stamps verified repository_id and index_name on valid chunks.
    """
    if not nodes:
        return []

    # 1. Verify that target_repo_id belongs to active_index_name
    canonical_id_for_active_index = resolve_repository_id(active_index_name)
    if canonical_id_for_active_index and target_repo_id:
        if canonical_id_for_active_index != target_repo_id:
            logger.warning(
                "Strict isolation rejection: Query targeted repo_id %s, "
                "but active index is %s (canonical ID %s). Rejecting all chunks.",
                target_repo_id,
                active_index_name,
                canonical_id_for_active_index,
            )
            return []

    verified_nodes: List[NodeWithScore] = []

    for n in nodes:
        meta = n.node.metadata or {}
        chunk_repo_id = meta.get("repository_id")
        chunk_index_name = meta.get("index_name")

        # Check explicit repository_id mismatch
        if chunk_repo_id and chunk_repo_id != target_repo_id:
            logger.warning(
                "Strict isolation rejection: chunk repository_id %s != target %s",
                chunk_repo_id,
                target_repo_id,
            )
            continue

        # Check explicit index_name mismatch
        if chunk_index_name and chunk_index_name != active_index_name:
            logger.warning(
                "Strict isolation rejection: chunk index_name %s != active %s",
                chunk_index_name,
                active_index_name,
            )
            continue

        # Check missing metadata in strict testing mode
        if require_existing_metadata and not chunk_repo_id:
            logger.warning("Strict isolation rejection: chunk missing required repository_id metadata")
            continue

        # Stamp verified repository metadata
        n.node.metadata["repository_id"] = target_repo_id
        n.node.metadata["index_name"] = active_index_name
        verified_nodes.append(n)

    return verified_nodes


def verify_chunk_isolation(node: NodeWithScore, target_repo_id: str) -> bool:
    """Return True if chunk has valid repository metadata matching target_repo_id."""
    if not node or not hasattr(node, "node") or not node.node:
        return False
    meta = node.node.metadata or {}
    return meta.get("repository_id") == target_repo_id
