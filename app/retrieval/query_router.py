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
from app.llm.prompts import QUERY_CLASSIFIER_PROMPT

logger = get_logger(__name__)


class QueryMode(Enum):
    CODE_LOOKUP    = "code_lookup"
    ARCHITECTURAL  = "architectural"
    RELATIONSHIP   = "relationship"


import yaml
import os

# Load router rules from YAML configuration
_RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "router_rules.yaml")
try:
    with open(_RULES_PATH, "r", encoding="utf-8") as _f:
        _rules = yaml.safe_load(_f)
except Exception as _e:
    logger.warning(f"Failed to load router rules from {_RULES_PATH}: {_e}")
    _rules = {}

_CODE_KEYWORDS = set(_rules.get("code_lookup", {}).get("keywords", []))
_ARCHITECTURAL_KEYWORDS = set(_rules.get("architectural", {}).get("keywords", []))
_STRONG_ARCHITECTURAL_PHRASES = set(_rules.get("architectural", {}).get("strong_phrases", []))
_GENERAL_OOS_PHRASES = set(_rules.get("out_of_scope", {}).get("general", []))
_ALWAYS_OOS_PHRASES = set(_rules.get("out_of_scope", {}).get("always", []))
_REPO_SCOPE_HINTS = set(_rules.get("repo_scope_hints", []))
_RELATIONSHIP_PHRASES = _rules.get("relationship", {}).get("phrases", [])
ADJECTIVE_MAPPING = _rules.get("adjective_mapping", {})


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

_RELATIONSHIP_PATTERNS = [re.compile(p) for p in _rules.get("relationship", {}).get("regex_patterns", [])]


def _is_relationship_query(query: str) -> bool:
    q = query.lower()
    for pat in _RELATIONSHIP_PATTERNS:
        if pat.search(q):
            return True
    if any(phrase in q for phrase in _RELATIONSHIP_PHRASES):
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
        prompt = QUERY_CLASSIFIER_PROMPT.format(query=query)
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


# Named constant for low-confidence similarity threshold.
# NOTE: This value is measured against the maximum similarity score of retrieved nodes
# (CrossEncoder sigmoid scores when USE_RERANKER=True, or Cosine similarity when False).
# TODO: This will need empirical tuning based on active retrieval/embeddings and query behavior.
LOW_CONFIDENCE_SIMILARITY_THRESHOLD = 0.40



ACTION_DISPLAY_NAMES = {
    "security_review": "Security Review",
    "tech_debt_scan": "Tech Debt Scan",
    "test_intelligence": "Test Intelligence",
    "dependency_graph": "Dependency Graph",
    "architecture_map": "Architecture Map",
    "business_flows": "Business Flows",
    "code_quality": "Code Quality",
    "impact_analysis": "Impact Analysis",
    "onboarding_guide": "Onboarding Guide",
    "api_documentation": "API Documentation",
    "engineering_report": "Engineering Report",
    "digital_twin": "Digital Twin",
}

def detect_excluded_folder(query: str) -> Optional[str]:
    """
    Check if the query references an excluded path segment in IGNORE_DIRS.
    Returns the name of the folder if matched, else None.
    """
    from app.ingestion.file_filter import IGNORE_DIRS
    
    q_lower = (query or "").lower()
    tokens = re.split(r'[\s\'"`(),;]', q_lower)
    for token in tokens:
        if not token:
            continue
        segments = token.replace("\\", "/").split("/")
        for seg in segments:
            if seg in IGNORE_DIRS:
                return seg
    return None

AGGREGATION_PATTERN = re.compile(
    r"\b(how\s+many|total\s+number\s+of|count\s+of|list\s+all)\b",
    re.IGNORECASE
)

def detect_aggregation(query: str) -> bool:
    """
    Check if the query matches aggregation/counting regex patterns.
    """
    return bool(AGGREGATION_PATTERN.search(query or ""))

SUPERLATIVE_PATTERN = re.compile(
    r"\b(most|least|best|worst|riskiest|messiest)\b",
    re.IGNORECASE
)

def has_superlative(query: str) -> bool:
    """
    Check if the query contains superlative keywords.
    """
    return bool(SUPERLATIVE_PATTERN.search(query or ""))

def match_adjective_action(query: str) -> Optional[str]:
    """
    Match adjective keywords from adjective mapping to an action key.
    """
    q_lower = (query or "").lower()
    for action, keywords in ADJECTIVE_MAPPING.items():
        if any(kw in q_lower for kw in keywords):
            return action
    return None

def classify_superlative_with_llm(query: str) -> Optional[str]:
    """
    LLM fallback classifier for superlative queries.
    Uses context-minimal prompt containing only query text and action names.
    """
    from llama_index.core import Settings
    
    actions_list = [
        "Architecture Map",
        "Security Review",
        "Business Flows",
        "Code Quality",
        "Impact Analysis",
        "Test Intelligence",
        "Onboarding Guide",
        "API Documentation",
        "Dependency Graph",
        "Engineering Report",
        "Tech Debt Scan",
        "Digital Twin"
    ]
    
    prompt = (
        "Classify the user's query into exactly one of these 12 intelligence actions "
        "if it is asking for a full-repo judgment/superlative analysis. "
        "If it does not match any action, respond with 'NONE'.\n\n"
        "Actions:\n" + "\n".join(f"- {a}" for a in actions_list) + "\n\n"
        f"Query: {query}\n\n"
        "Respond with ONLY the exact name of the matched action (e.g., 'Security Review'), or 'NONE'."
    )
    
    try:
        response = Settings.llm.complete(prompt)
        res = str(response).strip()
        for action in actions_list:
            if action.lower() in res.lower():
                return action.lower().replace(" ", "_")
    except Exception as e:
        logger.warning(f"LLM superlative classifier failed: {e}")
        
    return None

from collections import OrderedDict
import threading

class LRUCache:
    def __init__(self, capacity: int = 200):
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

_superlative_cache = LRUCache(200)

def _normalize_query(query: str) -> str:
    q = query.lower().strip()
    q = re.sub(r'[^\w\s]', '', q)
    return " ".join(q.split())


def check_superlative_intent(query: str, index_name: Optional[str] = None) -> Optional[dict]:
    """
    Check if the query is a judgment/superlative query that should route to
    a repository intelligence action.
    
    Returns a dict with suggested_action and message if matched, else None.
    """
    if not has_superlative(query):
        return None
        
    action_key = match_adjective_action(query)
    
    if not action_key:
        norm_query = _normalize_query(query)
        cache_key = (index_name or "", norm_query)
        
        cached_result = _superlative_cache.get(cache_key)
        if cached_result is not None:
            # We use a special marker for negative cache hit so we can return None
            # without confusing with a cache miss
            if cached_result == "NONE_ACTION":
                action_key = None
            else:
                action_key = cached_result
        else:
            action_key = classify_superlative_with_llm(query)
            # Populate cache
            if action_key is None:
                _superlative_cache.put(cache_key, "NONE_ACTION")
            else:
                _superlative_cache.put(cache_key, action_key)
        
    if action_key:
        display_name = ACTION_DISPLAY_NAMES.get(action_key, action_key.replace("_", " ").title())
        return {
            "suggested_action": action_key,
            "message": f"That needs a full-repo analysis — run {display_name}?"
        }
        
    return None


_identifier_cache = LRUCache(200)

def is_real_identifier(target: Optional[str], index_name: Optional[str]) -> bool:
    """
    Checks if the target is a real identifier (class, function, method, constant, config parameter)
    defined or present in the indexed codebase. Exact case-insensitive matching is used on the keys.
    Results are cached using thread-safe LRUCache.
    """
    if not target or not index_name:
        return False

    norm_target = target.strip().lower()
    cache_key = (index_name, norm_target)
    
    cached_result = _identifier_cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    from app.config import INDEX_DIR
    import json
    
    graph_path = os.path.join(INDEX_DIR, index_name, "relationship_graph.json")
    if not os.path.exists(graph_path):
        _identifier_cache.put(cache_key, False)
        return False

    try:
        with open(graph_path, "r", encoding="utf-8") as gf:
            graph = json.load(gf)
    except Exception as ex:
        logger.warning(f"Failed to load relationship graph: {ex}")
        _identifier_cache.put(cache_key, False)
        return False

    # Exact case-insensitive matching on graph keys
    res = any(k.lower() == norm_target for k in graph.keys())
    _identifier_cache.put(cache_key, res)
    return res
