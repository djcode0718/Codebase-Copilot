"""
api/routers/graph.py
─────────────────────
Relationship graph endpoints.

  GET  /api/repo/{repo_id}/relationship-graph        Full graph JSON
  GET  /api/repo/{repo_id}/relationship-graph/keys   Symbol key list only

The graph is pre-built by the indexing pipeline and stored at
  INDEX_DIR/{index_name}/relationship_graph.json
as a plain adjacency dict:  { "symbol_name": ["referencing/file.py", ...], ... }
"""

import json
import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.routers._repo_access import ensure_repo_access
from api.services import supabase_service
from app.config import INDEX_DIR
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


def _resolve_graph_path(supabase: Client, user_id: str, repo_id: str) -> str:
    """
    Resolve repo_id → index_name → relationship_graph.json path.
    Raises HTTPException 404 if the repo is not found, not accessible, or has
    no relationship graph on disk yet.
    """
    repo = ensure_repo_access(supabase, repo_id, user_id)
    index_name: str = repo.get("index_name", "")
    if not index_name:
        raise HTTPException(status_code=404, detail="Repository has no index name; it may not have been indexed yet.")

    graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
    if not os.path.exists(graph_path):
        raise HTTPException(
            status_code=404,
            detail="Relationship graph not found for this repository. Index the repository first.",
        )
    return graph_path


def _load_graph(graph_path: str) -> dict:
    """Load and return the adjacency dict from disk. Never raises on empty/malformed JSON."""
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        logger.warning(f"Unexpected type in relationship_graph.json at {graph_path}: {type(data)}")
        return {}
    except Exception as exc:
        logger.error(f"Failed to read relationship_graph.json at {graph_path}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to read relationship graph from disk.")


@router.get("/{repo_id}/relationship-graph")
async def get_relationship_graph(
    repo_id: str,
    supabase: Client = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    """
    Return the full relationship graph for a repository.

    Response:
        {
          "graph": {
            "symbol_or_file": ["referencing/path.py", ...],
            ...
          }
        }

    Returns 404 if the repository has not been indexed yet or was indexed before
    the relationship graph feature existed.
    """
    graph_path = _resolve_graph_path(supabase, user_id, repo_id)
    graph = _load_graph(graph_path)
    return {"graph": graph}


@router.get("/{repo_id}/relationship-graph/keys")
async def get_relationship_graph_keys(
    repo_id: str,
    supabase: Client = Depends(get_supabase),
    user_id: str = Depends(get_current_user),
):
    """
    Return only the symbol keys from the relationship graph.

    This is a lightweight endpoint used by the frontend to check whether a
    specific inline code tag is a known graph symbol, without downloading the
    entire adjacency data for every message render.

    Response:
        { "keys": ["symbol1", "symbol2", ...] }

    Returns 404 if the repository has not been indexed yet.
    """
    graph_path = _resolve_graph_path(supabase, user_id, repo_id)
    graph = _load_graph(graph_path)
    keys: List[str] = list(graph.keys())
    return {"keys": keys}
