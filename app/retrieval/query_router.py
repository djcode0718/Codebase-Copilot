"""
query_router.py
───────────────
Classifies incoming queries into one of two modes before retrieval:

  CODE_LOOKUP    → specific function/class/file questions
                   uses strict retrieval + "answer only from context" prompt
                   examples: "how does parse_documents work?",
                             "show me the vector store implementation"

  ARCHITECTURAL  → broad, creative, reasoning questions
                   uses relaxed retrieval + summary context + reasoning prompt
                   examples: "what are the limitations?",
                             "how can I improve this project?",
                             "what design patterns are used?"

The classifier is the LLM itself with a minimal prompt — zero extra model,
zero extra RAM, adds ~0.5s latency on local Ollama.
"""

from enum import Enum
from llama_index.core import Settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryMode(Enum):
    CODE_LOOKUP    = "code_lookup"
    ARCHITECTURAL  = "architectural"


# Keywords that strongly signal a CODE_LOOKUP query
# Used as a fast pre-check before calling the LLM classifier
_CODE_KEYWORDS = {
    "function", "method", "class", "def ", "import", "variable",
    "implement", "code", "file", "module", "error", "bug", "fix",
    "return", "parameter", "argument", "loop", "call", "usage",
    "how does", "show me", "where is", "what does", "explain the",
    "find", "locate"
}

_ARCHITECTURAL_KEYWORDS = {
    "limitation", "improve", "improvement", "better", "optimize",
    "architecture", "design", "pattern", "suggest", "recommend",
    "weakness", "problem", "issue", "missing", "add", "future",
    "scale", "performance", "tradeoff", "compare", "overview",
    "summarize", "summary", "what is this", "what does this project"
}

_CLASSIFIER_PROMPT = """You are a query classifier for a codebase Q&A system.
Classify the following query into exactly one of these two categories:

CODE_LOOKUP: Questions about specific code — functions, classes, files,
             implementations, bugs, usage, or anything that requires
             finding a specific piece of code to answer.

ARCHITECTURAL: Broad questions about the project — limitations, improvements,
               design patterns, architecture, suggestions, comparisons,
               or questions that require reasoning about the codebase as a whole.

Query: {query}

Respond with ONLY the category name: CODE_LOOKUP or ARCHITECTURAL"""


def classify_query(query: str) -> QueryMode:
    """
    Two-stage classification:
    1. Fast keyword check — avoids LLM call for obvious cases
    2. LLM classifier — for ambiguous queries
    """
    query_lower = query.lower()

    # Stage 1: Fast keyword pre-check
    arch_score = sum(1 for kw in _ARCHITECTURAL_KEYWORDS if kw in query_lower)
    code_score = sum(1 for kw in _CODE_KEYWORDS if kw in query_lower)

    if arch_score > code_score and arch_score >= 2:
        logger.info(f"Query classified as ARCHITECTURAL (keyword fast-path, score={arch_score})")
        return QueryMode.ARCHITECTURAL

    if code_score > arch_score and code_score >= 2:
        logger.info(f"Query classified as CODE_LOOKUP (keyword fast-path, score={code_score})")
        return QueryMode.CODE_LOOKUP

    # Stage 2: LLM classifier for ambiguous cases
    try:
        llm = Settings.llm
        prompt = _CLASSIFIER_PROMPT.format(query=query)
        response = llm.complete(prompt)
        result = str(response).strip().upper()

        if "ARCHITECTURAL" in result:
            logger.info("Query classified as ARCHITECTURAL (LLM classifier)")
            return QueryMode.ARCHITECTURAL
        else:
            logger.info("Query classified as CODE_LOOKUP (LLM classifier)")
            return QueryMode.CODE_LOOKUP

    except Exception as e:
        # Safe fallback — CODE_LOOKUP is the more conservative mode
        logger.warning(f"LLM classifier failed: {e} — defaulting to CODE_LOOKUP")
        return QueryMode.CODE_LOOKUP