"""
Unit tests for api/services/chat_stream_utils.py

Covers:
- is_rate_limit_error: various rate-limit signals
- safe_chat_error_message: all error classification branches
- to_sse_data: JSON serialisation and SSE framing
- parse_sse_data_line: valid, invalid, and edge-case inputs
- Negative paths: malformed / unexpected input handling
"""

from __future__ import annotations

import json
import pytest

from api.services.chat_stream_utils import (
    is_rate_limit_error,
    safe_chat_error_message,
    to_sse_data,
    parse_sse_data_line,
)


# ─── is_rate_limit_error ────────────────────────────────────────────────────

class TestIsRateLimitError:
    def test_rate_limit_phrase(self):
        assert is_rate_limit_error(Exception("rate limit exceeded"))

    def test_rate_limit_underscore(self):
        assert is_rate_limit_error(Exception("rate_limit_exceeded on groq"))

    def test_too_many_requests(self):
        assert is_rate_limit_error(Exception("too many requests"))

    def test_429_code(self):
        assert is_rate_limit_error(Exception("error code: 429"))

    def test_quota_exceeded(self):
        assert is_rate_limit_error(Exception("quota exceeded for today"))

    def test_unrelated_error_false(self):
        assert not is_rate_limit_error(Exception("connection refused"))

    def test_empty_message_false(self):
        assert not is_rate_limit_error(Exception(""))

    def test_case_insensitive(self):
        assert is_rate_limit_error(Exception("Rate Limit Exceeded"))


# ─── safe_chat_error_message ────────────────────────────────────────────────

class TestSafeChatErrorMessage:
    def test_rate_limit_returns_retry_message(self):
        msg = safe_chat_error_message(Exception("rate limit exceeded"))
        assert "rate-limited" in msg.lower() or "retry" in msg.lower()

    def test_rate_limit_suppressed_when_flag_false(self):
        msg = safe_chat_error_message(
            Exception("rate limit exceeded"), include_rate_limit=False
        )
        # Should fall through to the generic message
        assert "internal error" in msg.lower()

    def test_memory_schema_error_conversation_summaries(self):
        msg = safe_chat_error_message(
            Exception("could not find the table 'conversation_summaries'")
        )
        assert "repository memory" in msg.lower() or "repository-specific" in msg.lower()

    def test_memory_schema_error_pgrst(self):
        msg = safe_chat_error_message(Exception("pgrst: schema cache mismatch"))
        assert "repository memory" in msg.lower() or "repository-specific" in msg.lower()

    def test_provider_bootstrap_no_api_key(self):
        msg = safe_chat_error_message(Exception("no api key found for provider"))
        assert "provider" in msg.lower() or "retry" in msg.lower()

    def test_provider_bootstrap_could_not_load(self):
        msg = safe_chat_error_message(Exception("could not load ollama model"))
        assert "provider" in msg.lower() or "retry" in msg.lower()

    def test_generic_fallback(self):
        msg = safe_chat_error_message(Exception("unexpected segfault"))
        assert "internal error" in msg.lower()

    def test_returns_string(self):
        assert isinstance(safe_chat_error_message(Exception("x")), str)


# ─── to_sse_data ─────────────────────────────────────────────────────────────

class TestToSseData:
    def test_basic_serialisation(self):
        result = to_sse_data({"type": "token", "content": "hello"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

    def test_roundtrip(self):
        payload = {"type": "done", "latency": 123}
        line = to_sse_data(payload)
        assert json.loads(line[6:].strip()) == payload

    def test_empty_dict(self):
        result = to_sse_data({})
        assert result == "data: {}\n\n"

    def test_nested_payload(self):
        payload = {"files": ["a.py", "b.py"], "meta": {"mode": "code_lookup"}}
        line = to_sse_data(payload)
        decoded = json.loads(line[6:].strip())
        assert decoded == payload

    def test_unicode_content(self):
        result = to_sse_data({"msg": "hello_world"})
        assert "hello_world" in result


# ─── parse_sse_data_line ────────────────────────────────────────────────────

class TestParseSseDataLine:
    def test_valid_json_line(self):
        line = 'data: {"type": "token", "content": "hi"}'
        result = parse_sse_data_line(line)
        assert result == {"type": "token", "content": "hi"}

    def test_missing_prefix_returns_none(self):
        assert parse_sse_data_line('{"type": "token"}') is None

    def test_empty_string_returns_none(self):
        assert parse_sse_data_line("") is None

    def test_invalid_json_returns_none(self):
        assert parse_sse_data_line("data: not-valid-json{{{") is None

    def test_empty_json_object(self):
        assert parse_sse_data_line("data: {}") == {}

    def test_roundtrip_from_to_sse_data(self):
        payload = {"type": "metadata", "latency_ms": 200}
        line = to_sse_data(payload).strip()
        result = parse_sse_data_line(line)
        assert result == payload

    def test_non_data_prefix_returns_none(self):
        assert parse_sse_data_line("event: ping") is None

    def test_data_only_prefix_returns_none(self):
        assert parse_sse_data_line("data:") is None
