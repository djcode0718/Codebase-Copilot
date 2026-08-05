"""
Conversation summary and entity extraction helpers.

This module intentionally keeps summarization deterministic and lightweight
so it can run on every turn without blocking chat streaming.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Any

FILE_RE = re.compile(r"\b[\w./-]+\.(?:py|ts|tsx|js|jsx|md|json|yaml|yml|sql)\b")
CLASS_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]+(?:Service|Controller|Manager|Repository|Client)?\b")
SERVICE_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*Service)\b")
MODULE_RE = re.compile(r"\b(?:app|api|frontend|tests)(?:\/[\w.-]+)+\b")
API_RE = re.compile(r"\/(?:api|v\d+)(?:\/[A-Za-z0-9_.-]+)+")
DECISION_RE = re.compile(r"\b(?:should|must|decided|decision|recommend|prefer)\b", re.IGNORECASE)
RISK_RE = re.compile(r"\b(?:risk|vulnerability|bug|regression|failure|outage|leak|security)\b", re.IGNORECASE)
ACTION_RE = re.compile(r"\b(?:task|next step|action|follow up|implement|add test|fix)\b", re.IGNORECASE)


def _top_words(text: str, max_items: int = 8) -> List[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", text.lower())
    stop = {
        "that", "this", "with", "from", "have", "there", "which", "about", "should",
        "would", "could", "their", "when", "where", "what", "into", "also", "your",
        "chat", "repo", "repository", "codebase", "session", "question", "answer",
    }
    filtered = [w for w in words if w not in stop]
    return [w for w, _ in Counter(filtered).most_common(max_items)]


def _unique_sorted(items: List[str], max_items: int = 20) -> List[str]:
    unique = []
    seen = set()
    for item in items:
        value = item.strip().strip("` ")
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
        if len(unique) >= max_items:
            break
    return unique


def build_conversation_summary(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not messages:
        return {
            "executive_summary": "No conversation history yet.",
            "technical_summary": "No technical details captured yet.",
            "key_decisions": [],
            "action_items": [],
            "risks_identified": [],
            "files_discussed": [],
            "services_discussed": [],
            "modules_discussed": [],
            "classes_discussed": [],
            "apis_discussed": [],
            "keywords": [],
            "tags": [],
        }

    text_parts: List[str] = []
    user_lines: List[str] = []
    assistant_lines: List[str] = []
    for m in messages[-30:]:
        role = (m.get("role") or "").lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        text_parts.append(content)
        first_sentence = content.split("\n", 1)[0][:240]
        if role == "user":
            user_lines.append(first_sentence)
        elif role == "assistant":
            assistant_lines.append(first_sentence)

    joined = "\n".join(text_parts)
    files = _unique_sorted(FILE_RE.findall(joined))
    services = _unique_sorted(SERVICE_RE.findall(joined))
    modules = _unique_sorted(MODULE_RE.findall(joined))
    classes = _unique_sorted(CLASS_RE.findall(joined))
    apis = _unique_sorted(API_RE.findall(joined))

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", joined) if s.strip()]
    key_decisions = [s[:300] for s in sentences if DECISION_RE.search(s)][:5]
    action_items = [s[:300] for s in sentences if ACTION_RE.search(s)][:6]
    risks = [s[:300] for s in sentences if RISK_RE.search(s)][:6]

    topic_hint = user_lines[-1] if user_lines else "repository discussion"
    exec_summary = f"Conversation focuses on {topic_hint[:120]}."
    tech_summary = (
        f"Discussed {len(files)} files, {len(services)} services, {len(classes)} classes, "
        f"and {len(apis)} API paths across the session."
    )

    keywords = _top_words(joined, max_items=10)
    tags = _unique_sorted(keywords + ["conversation-memory", "repository-intelligence"], max_items=12)

    return {
        "executive_summary": exec_summary,
        "technical_summary": tech_summary,
        "key_decisions": key_decisions,
        "action_items": action_items,
        "risks_identified": risks,
        "files_discussed": files,
        "services_discussed": services,
        "modules_discussed": modules,
        "classes_discussed": classes,
        "apis_discussed": apis,
        "keywords": keywords,
        "tags": tags,
    }
