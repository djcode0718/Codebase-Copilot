"""
api/routers/suggestions.py
───────────────────────────
Generates suggested questions for a repository using the codebase context document.

  GET /api/repo/{repo_id}/suggestions

Returns 6 clickable question chips for the frontend.
Questions are generated once after indexing and cached in the DB / in-process.

The architectural context doc built by context_builder.py is the source —
it contains file summaries, tech stack, and function names, which lets the
LLM produce highly specific questions rather than generic ones.
"""

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from api.dependencies import get_current_user, get_supabase
from api.services.supabase_service import get_repo
from app.config import INDEX_DIR
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# In-process cache: repo_id → list of question strings
_suggestions_cache: dict = {}

_SUGGESTION_PROMPT = """You are helping a developer understand a new codebase.
Based on the codebase context below, generate exactly 6 specific, useful questions
that a developer would want to ask about this project.

Rules:
- Mix code-level questions (e.g. "How does X function work?") with architectural questions
- Be specific to THIS codebase — use actual file names, class names, or concepts from the context
- Keep each question under 10 words
- No numbering, no bullets — just the question text

Codebase context:
{context}

Output exactly 6 questions, one per line, nothing else."""


async def _generate_suggestions(context: str) -> List[str]:
    """Call the LLM to generate questions from the codebase context."""
    from app.llm.llm_client import configure_llamaindex_settings
    from app.services.llm_fallback import generate_with_fallback

    # Never touch Settings.llm lazily; force app-configured providers first.
    configure_llamaindex_settings()

    prompt = _SUGGESTION_PROMPT.format(context=context[:3000])  # cap context size

    try:
        raw = (await generate_with_fallback(prompt)).strip()
        questions = [q.strip() for q in raw.split("\n") if q.strip()]
        # Filter out any lines that look like preamble
        questions = [q for q in questions if q.endswith("?")][:6]

        # Fallback if LLM didn't return enough
        if len(questions) < 3:
            questions = _default_suggestions()

        return questions

    except Exception as e:
        logger.warning(f"Suggestion generation failed: {e}")
        return _default_suggestions()


def _default_suggestions() -> List[str]:
    """Fallback questions used when LLM generation fails."""
    return [
        "Explain the overall architecture of this project.",
        "What are the main limitations of this codebase?",
        "How does the code pipeline work?",
        "Which files are most important to understand first?",
        "What would you improve to make this production-ready?",
        "How does the query routing logic work?",
    ]


def _load_context_doc(index_name: str) -> Optional[str]:
    """Load the codebase_context.txt from disk (built during indexing)."""
    cache_path = os.path.join(INDEX_DIR, index_name, "codebase_context.txt")
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Could not read context doc: {e}")
        return None


@router.get("/{repo_id}/suggestions")
async def get_suggestions(
    repo_id: str,
    user_id: str = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Returns 6 suggested questions tailored to the indexed repository.

    Response:
        { "questions": ["...", "...", ...] }

    Questions are generated from the codebase context document and cached
    in-process. Subsequent calls return the cached list instantly.
    """
    # Check cache first
    if repo_id in _suggestions_cache:
        return {"questions": _suggestions_cache[repo_id]}

    # Verify repo access
    repo = get_repo(supabase, repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if repo["status"] != "ready":
        return {"questions": _default_suggestions()}

    index_name = repo["index_name"]

    # Load context doc and generate questions
    context = _load_context_doc(index_name)
    if context:
        questions = await _generate_suggestions(context)
    else:
        # Context doc not found — use defaults
        logger.warning(f"No context doc found for '{index_name}' — using defaults")
        questions = _default_suggestions()

    # Cache for this session
    _suggestions_cache[repo_id] = questions

    return {"questions": questions}
