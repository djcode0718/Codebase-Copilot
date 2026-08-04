"""
api/services/chat_stream_utils.py
Shared SSE formatting and chat-safe error mapping utilities.
"""

import json
from typing import Any, Dict, Optional

_MEMORY_SCHEMA_ERROR_TOKENS = (
    "could not find the table",
    "schema cache",
    "pgrst",
    "conversation_summaries",
    "conversation_tags",
)


def is_rate_limit_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "rate limit" in msg
        or "rate_limit_exceeded" in msg
        or "too many requests" in msg
        or "error code: 429" in msg
        or "quota" in msg
    )


def safe_chat_error_message(err: Exception, *, include_rate_limit: bool = True) -> str:
    """Convert internal exceptions to user-safe, actionable chat guidance."""
    msg_l = str(err).lower()

    if include_rate_limit and is_rate_limit_error(err):
        return "The model provider is rate-limited right now. Please retry in a moment."

    if any(token in msg_l for token in _MEMORY_SCHEMA_ERROR_TOKENS):
        return (
            "I hit a temporary repository memory issue. "
            "Please ask a repository-specific question about a file, function, class, or module."
        )

    return (
        "I ran into an internal error while answering. "
        "Please retry with a repository-specific question (file, function, class, or module)."
    )


def to_sse_data(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\\n\\n"


def parse_sse_data_line(sse_line: str) -> Optional[Dict[str, Any]]:
    if not sse_line.startswith("data: "):
        return None
    try:
        return json.loads(sse_line[6:])
    except Exception:
        return None

