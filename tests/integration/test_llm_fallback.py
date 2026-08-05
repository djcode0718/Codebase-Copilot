import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

pytestmark = pytest.mark.slow
pytest.importorskip("llama_index.core")

from llama_index.core.llms import CompletionResponse

from app.services.llm_fallback import (
    ResilientFallbackLLM,
    AllModelsExhaustedError,
    parse_retry_delay,
    is_rate_limit_or_quota_error,
)

# --- Helper Mock LLM Creator ---
def create_mock_llm(model_name: str, provider: str = "MockProvider"):
    mock_llm = MagicMock()
    mock_llm.__class__.__name__ = provider
    mock_llm.model = model_name
    mock_llm.complete = MagicMock()
    mock_llm.stream_complete = MagicMock()
    
    # Async mock methods
    mock_llm.acomplete = AsyncMock()
    mock_llm.astream_complete = MagicMock()
    
    return mock_llm

def make_completion_response(text: str) -> CompletionResponse:
    return CompletionResponse(text=text)

# --- Helper Mock Generators ---
def mock_stream_generator(chunks: list):
    for chunk in chunks:
        yield CompletionResponse(text=chunk, delta=chunk)

async def mock_async_stream_generator(chunks: list):
    for chunk in chunks:
        yield CompletionResponse(text=chunk, delta=chunk)


# --- Unit Tests ---

def test_parse_retry_delay():
    # Gemini protobuf format
    err_gemini = Exception("ResourceExhausted: 429 quota exceeded. retry_delay { seconds: 28 }")
    assert parse_retry_delay(err_gemini) == 28

    # Groq text format
    err_groq = Exception("Rate limit reached. Please try again in 4.5s.")
    assert parse_retry_delay(err_groq) == 4

    # Generic format
    err_generic = Exception("Too many requests. Retry after 5 seconds.")
    assert parse_retry_delay(err_generic) == 5

    # None
    assert parse_retry_delay(Exception("Generic error message")) is None


def test_is_rate_limit_or_quota_error():
    assert is_rate_limit_or_quota_error(Exception("429 rate limit exceeded")) is True
    assert is_rate_limit_or_quota_error(Exception("quota limit reached")) is True
    assert is_rate_limit_or_quota_error(Exception("resource exhausted")) is True
    assert is_rate_limit_or_quota_error(Exception("Auth credential invalid")) is False


def test_fallback_happy_path():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    llm1.complete.return_value = make_completion_response("Primary Success")
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])
    res = pipeline.complete("test prompt")
    
    assert res.text == "Primary Success"
    llm1.complete.assert_called_once()
    llm2.complete.assert_not_called()


def test_fallback_on_429():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    llm1.complete.side_effect = Exception("429 Rate limit exceeded")
    llm2.complete.return_value = make_completion_response("Fallback Success")
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])
    res = pipeline.complete("test prompt")
    
    assert res.text == "Fallback Success"
    assert llm1.complete.call_count == 1  # 1 initial and immediately move to fallback because retry_delay is None
    llm2.complete.assert_called_once()


def test_fallback_non_rate_limit_tries_next_model():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    llm1.complete.side_effect = ValueError("Invalid auth token")
    llm2.complete.return_value = make_completion_response("Fallback after startup error")
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])

    res = pipeline.complete("test prompt")
    assert res.text == "Fallback after startup error"
    llm1.complete.assert_called_once()
    llm2.complete.assert_called_once()


def test_fallback_respects_retry_delay_short(monkeypatch):
    # Mock sleep to run fast
    mock_sleep = MagicMock()
    monkeypatch.setattr("time.sleep", mock_sleep)

    llm1 = create_mock_llm("gemini-3.6-flash")
    # First try throws 429 with short delay, second try succeeds
    llm1.complete.side_effect = [
        Exception("429 rate limited. retry_delay { seconds: 4 }"),
        make_completion_response("Success on retry")
    ]
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1])
    res = pipeline.complete("test prompt")
    
    assert res.text == "Success on retry"
    assert llm1.complete.call_count == 2
    mock_sleep.assert_called_once_with(4)


def test_fallback_ignores_retry_delay_long(monkeypatch):
    mock_sleep = MagicMock()
    monkeypatch.setattr("time.sleep", mock_sleep)

    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    # First model has a long delay (30s) so it should transition directly
    llm1.complete.side_effect = Exception("429 rate limited. retry_delay { seconds: 30 }")
    llm2.complete.return_value = make_completion_response("Fallback Success")
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])
    res = pipeline.complete("test prompt")
    
    assert res.text == "Fallback Success"
    assert llm1.complete.call_count == 1  # No retry because 30s is over the 10s limit
    mock_sleep.assert_not_called()
    llm2.complete.assert_called_once()


def test_all_models_exhausted_raises_error():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    llm1.complete.side_effect = Exception("429 Model 1 rate limit")
    llm2.complete.side_effect = Exception("429 Model 2 rate limit")
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])
    
    with pytest.raises(AllModelsExhaustedError) as exc_info:
        pipeline.complete("test prompt")
        
    assert "All LLM models in the fallback chain were exhausted" in str(exc_info.value)
    assert len(exc_info.value.errors) == 2


# --- Async & Streaming Unit Tests ---

@pytest.mark.asyncio
async def test_async_fallback_happy_path():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm1.acomplete.return_value = make_completion_response("Async Success")
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1])
    res = await pipeline.acomplete("test prompt")
    
    assert res.text == "Async Success"
    llm1.acomplete.assert_called_once()


@pytest.mark.asyncio
async def test_async_stream_fallback_before_yield():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    # Model 1 fails immediately on stream creation
    llm1.astream_complete.side_effect = Exception("429 rate limit")
    
    # Model 2 succeeds
    async def mock_success_stream(*args, **kwargs):
        yield CompletionResponse(text="Hello", delta="Hello")
        yield CompletionResponse(text=" World", delta=" World")
    llm2.astream_complete.side_effect = mock_success_stream
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])
    
    chunks = []
    stream_res = pipeline.astream_complete("test prompt")
    async for chunk in stream_res:
        chunks.append(chunk.text)
        
    assert chunks == ["Hello", " World"]
    llm1.astream_complete.assert_called_once()
    llm2.astream_complete.assert_called_once()


@pytest.mark.asyncio
async def test_async_stream_aborts_mid_stream():
    llm1 = create_mock_llm("gemini-3.6-flash")
    llm2 = create_mock_llm("gemini-3-flash")
    
    # Model 1 yields one token then crashes mid-stream
    async def mock_crashing_stream(*args, **kwargs):
        yield CompletionResponse(text="Start", delta="Start")
        raise Exception("429 Mid-stream quota limit reached")
        
    llm1.astream_complete.side_effect = mock_crashing_stream
    
    pipeline = ResilientFallbackLLM(fallback_chain=[llm1, llm2])
    
    chunks = []
    with pytest.raises(Exception, match="Mid-stream quota limit reached"):
        stream_res = pipeline.astream_complete("test prompt")
        async for chunk in stream_res:
            chunks.append(chunk.text)
            
    assert chunks == ["Start"]
    llm1.astream_complete.assert_called_once()
    llm2.astream_complete.assert_not_called()  # Never fallback mid-response!
