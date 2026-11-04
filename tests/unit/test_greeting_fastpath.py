"""Unit tests for greeting fast path in query routing and chat stream."""
import pytest
from app.retrieval.query_router import detect_greeting, classify_query, QueryMode, GREETING_RESPONSE


def test_detect_greeting_positive():
    greetings = [
        "hi", "Hi", "HI", "hi!", "hello", "Hello", "hello?", "hey", "Hey",
        "good morning", "good evening", "hi there", "hello there", "what's up"
    ]
    for g in greetings:
        assert detect_greeting(g) is True, f"Failed for {g}"


def test_detect_greeting_negative():
    non_greetings = [
        "What is this repository about?",
        "Where is the main application entry point?",
        "How does authentication work?",
        "history of commits",
        "hide the button",
        "hiking trails"
    ]
    for q in non_greetings:
        assert detect_greeting(q) is False, f"Failed for {q}"


def test_classify_query_greeting_fast_path():
    # Should classify to CODE_LOOKUP without calling LLM
    assert classify_query("hi") == QueryMode.CODE_LOOKUP
    assert classify_query("hello") == QueryMode.CODE_LOOKUP
    assert classify_query("hey there!") == QueryMode.CODE_LOOKUP


@pytest.mark.asyncio
async def test_stream_chat_greeting_early_exit():
    from api.services.chat_service import stream_chat_response

    events = []
    async for sse in stream_chat_response(
        query="hi",
        index_name="whisper",
        repo_id="test-repo",
        chat_id="test-chat",
    ):
        events.append(sse)

    full_output = "".join(events)
    assert "token" in full_output
    assert "Hello! I am your Codebase Copilot" in full_output
    assert "done" in full_output
