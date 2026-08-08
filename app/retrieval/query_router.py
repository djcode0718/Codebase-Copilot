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
from typing import Optional
from llama_index.core import Settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QueryMode(Enum):
    CODE_LOOKUP    = "code_lookup"
    ARCHITECTURAL  = "architectural"
    RELATIONSHIP   = "relationship"


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
    "limitation", "limitations", "improve", "improvement", "better", "optimize",
    "architecture", "architectural", "design", "pattern", "suggest", "recommend",
    "weakness", "weaknesses", "problem", "issue", "missing", "add", "future",
    "scale", "performance", "tradeoff", "tradeoffs", "trade-off", "trade-offs",
    "compare", "overview", "summarize", "summary", "what is this", "what does this project",
    "technical debt", "debt", "roadmap", "business impact", "severity",
    "prioritized", "prioritised", "categorize", "category",
    "knowledge graph", "business flow", "digital twin", "repository health",
    "pipeline", "rag", "system"
}

_STRONG_ARCHITECTURAL_PHRASES = {
    "technical debt",
    "business flow",
    "knowledge graph",
    "digital twin",
    "executive summary",
    "architecture diagram",
    "architectural diagram",
    "repository health",
    "limitation",
    "limitations",
    "weakness",
    "weaknesses",
    "tradeoff",
    "tradeoffs",
    "trade-off",
    "trade-offs",
    "architecture",
    "architectural"
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

_GENERAL_OOS_PHRASES = {
    "share me good movies list",
    "good movies list",
    "movie list",
    "movie recommendations",
    "do you like",
    "what do you like",
    "what is your favorite",
    "what's your favorite",
    "which do you prefer",
    "do you prefer",
    "tell me a joke",
    "how are you",
    "who are you",
    "what is the weather",
    "what's the weather",
}

_ALWAYS_OOS_PHRASES = {
    "tell me a joke",
    "how are you",
    "who are you",
    "what is the weather",
    "what's the weather",
}

# Keep OOS heuristics from grabbing legitimate repository questions.
_REPO_SCOPE_HINTS = {
    "repo", "repository", "codebase", "project", "this project", "this repo",
    "file", "files", "function", "functions", "class", "classes", "module", "modules",
    "method", "methods", "api", "endpoint", "service", "component", "architecture",
    "implementation", "bug", "fix", "frontend", "backend", "pipeline", "rag", "llm",
}


import re


def is_general_knowledge_or_preference_query(query: str) -> bool:
    """Detect clearly out-of-scope small-talk, personal preference, or GK asks.

    This keeps broad repository architecture questions working while short-circuiting
    prompts that should not route into codebase persona responses.
    """
    text = (query or "").strip().lower()
    if not text:
        return False

    has_repo_scope = any(hint in text for hint in _REPO_SCOPE_HINTS)

    if any(phrase in text for phrase in _ALWAYS_OOS_PHRASES):
        return True

    if any(phrase in text for phrase in _GENERAL_OOS_PHRASES) and not has_repo_scope:
        return True

    # Catch generic recommendation/list asks (movies/books/music/etc.).
    if not has_repo_scope:
        has_oos_topic = re.search(
            r"\b(movie|movies|film|films|book|books|music|song|songs|anime|series|shows?)\b",
            text,
        )
        has_oos_intent = re.search(
            r"\b(share|suggest|recommend|recommendation|recommendations|give|list|top|best|good)\b",
            text,
        )
        if has_oos_topic and has_oos_intent:
            return True

    # Prefer strict phrase matches first; keep lightweight regexes minimal.
    if re.match(r"^(do|did|can)\s+you\s+(like|prefer)\b", text) and not has_repo_scope:
        return True
    if re.match(r"^what\s+is\s+your\s+(favorite|favourite)\b", text) and not has_repo_scope:
        return True
    if re.match(r"^(who\s+won|capital\s+of|what\s+is\s+the\s+capital\s+of)\b", text) and not has_repo_scope:
        return True
    return False

def _is_relationship_query(query: str) -> bool:
    q = query.lower()
    patterns = [
        # Match "what functions/modules/code call/calls/import/imports/use/uses/reference/references/instantiate/instantiates/create/creates X"
        r"\b(?:what|who|which)\s+(?:functions|modules|files|classes|methods|code|packages|elements)?\s*(?:call|calls|import|imports|use|uses|depend|depends|reference|references|instantiate|instantiates|create|creates)\b",
        # Match "where/how is X called/imported/used/referenced/instantiated/created"
        r"\b(?:where|how)\s+is\s+.*\s+(?:called|imported|used|referenced|instantiated|created)\b",
        # Match "what breaks/is affected if I delete/deleted/remove/removed X"
        r"\bwhat\s+(?:would\s+)?(?:break|be\s+affected)\s+if\s+.*\s+(?:delete|deleted|remove|removed)\b",
        # Match "who depends on X" or "who imports X"
        r"\bwho\s+depends\s+on\b",
        # Match "dependencies/dependents/imports/callers of X"
        r"\b(?:dependencies|dependents|imports|callers)\s+of\b",
        # Additional pattern for "which modules depend on X"
        r"\bwhich\s+modules?\s+depend(?:s)?\s+on\b",
    ]
    for pat in patterns:
        if re.search(pat, q):
            return True
    
    phrases = [
        "what calls ", "who calls ", "where is called", "what imports ",
        "who imports ", "what depends on ", "who uses ", "what breaks if",
        "what would break if", "what is affected if", "which modules depend on",
        "who instantiates", "what instantiates", "who creates", "what creates",
    ]
    if any(phrase in q for phrase in phrases):
        return True
    return False


def extract_relationship_target(query: str) -> Optional[str]:
    q = query.strip().rstrip("?").strip()

    stop_words = {
        "the", "a", "an", "it", "is", "to", "for", "of", "in", "on",
        "class", "function", "method", "module", "file", "package", "variable", "object", "code"
    }

    # 1. Prefer quoted identifiers
    quoted = re.findall(r'["\']([a-zA-Z0-9_\-\.\/]+)["\']', q)
    if quoted:
        return quoted[0]

    # 2. Look for patterns where a relationship verb is followed by a symbol
    patterns = [
        # verb + target
        r"\b(?:call|calls|import|imports|use|uses|depend\s+on|depends\s+on|delete|deleted|remove|removed|instantiate|instantiates|create|creates)\s+([a-zA-Z0-9_\-\.\/]+)\b",
        # where/how is <target> called/imported/used/referenced/instantiated/created
        r"\b(?:where|how)\s+is\s+([a-zA-Z0-9_\-\.\/]+)\s+(?:called|imported|used|referenced|instantiated|created)\b",
    ]
    for pat in patterns:
        m = re.search(pat, q, re.IGNORECASE)
        if m:
            val = m.group(1)
            if val.lower() not in stop_words:
                return val

    # 3. Fallback: last identifier-like token that is not a stop word or code descriptor
    words = [w.strip("`'\".,()?") for w in q.split() if w]
    for w in reversed(words):
        if w.lower() in stop_words:
            continue
        if re.fullmatch(r"[a-zA-Z0-9_\-\.\/]+", w):
            return w
    return None


def classify_query(query: str) -> QueryMode:
    """
    Two-stage classification with RELATIONSHIP mode check:
    1. Relationship check (Stage -1)
    2. Fast keyword check — avoids LLM call for obvious cases
    3. LLM classifier — for ambiguous queries
    """
    query_lower = query.lower()

    if _is_relationship_query(query):
        logger.info("Query classified as RELATIONSHIP")
        return QueryMode.RELATIONSHIP

    # Stage 0: strong high-level intent phrases should never fall back to code lookup.
    if any(phrase in query_lower for phrase in _STRONG_ARCHITECTURAL_PHRASES):
        logger.info("Query classified as ARCHITECTURAL (strong-phrase fast-path)")
        return QueryMode.ARCHITECTURAL

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
