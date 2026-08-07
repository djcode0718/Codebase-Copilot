from fastapi import HTTPException
from supabase import Client

from api.services import supabase_service


def ensure_repo_access(supabase: Client, repo_id: str, user_id: str) -> dict:
    """Return repository if it exists and belongs to the current user."""
    repo = supabase_service.get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return repo
