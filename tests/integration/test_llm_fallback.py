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
    mock_llm._cb_provider = provider
    mock_llm._cb_model_name = model_name
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


@pytest.mark.asyncio
async def test_concurrent_last_llm_usage():
    import asyncio
    from app.services.llm_fallback import _record_llm_usage, get_last_llm_usage
    
    async def request_one():
        _record_llm_usage("ProviderA", "ModelA")
        await asyncio.sleep(0.1)
        usage = get_last_llm_usage()
        return usage
        
    async def request_two():
        await asyncio.sleep(0.05)
        _record_llm_usage("ProviderB", "ModelB")
        await asyncio.sleep(0.1)
        usage = get_last_llm_usage()
        return usage

    usage1, usage2 = await asyncio.gather(request_one(), request_two())
    
    assert usage1 == {"provider": "ProviderA", "model": "ModelA"}
    assert usage2 == {"provider": "ProviderB", "model": "ModelB"}


# ─── Seven-Model Fallback Chain Verification Tests ────────────────────────────

from app.services.llm_fallback import reset_circuit_breakers, is_circuit_open


@pytest.fixture(autouse=True)
def clean_circuits():
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


def test_gemini_model_specific_error_advances_to_next_gemini_model():
    """Gemini 3.8 Flash model-specific error (404/not found) must advance to Gemini 3.7 Flash."""
    m1 = create_mock_llm("gemini-3.8-flash", provider="gemini")
    m2 = create_mock_llm("gemini-3.7-flash", provider="gemini")
    m3 = create_mock_llm("gemini-3.6-flash", provider="gemini")
    groq1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")

    # M1 fails with 404 Not Found (model-specific)
    m1.complete.side_effect = Exception("404 NotFound: models/gemini-3.8-flash is not found")
    # M2 succeeds
    m2.complete.return_value = make_completion_response("Gemini 3.7 Success")

    pipeline = ResilientFallbackLLM(fallback_chain=[m1, m2, m3, groq1])
    res = pipeline.complete("test prompt")

    assert res.text == "Gemini 3.7 Success"
    m1.complete.assert_called_once()
    m2.complete.assert_called_once()
    m3.complete.assert_not_called()
    groq1.complete.assert_not_called()


def test_gemini_quota_exhaustion_skips_remaining_gemini_models_to_groq():
    """Gemini quota exhaustion (429 / ResourceExhausted) must skip remaining Gemini models and move directly to Groq."""
    m1 = create_mock_llm("gemini-3.8-flash", provider="gemini")
    m2 = create_mock_llm("gemini-3.7-flash", provider="gemini")
    m3 = create_mock_llm("gemini-3.6-flash", provider="gemini")
    groq1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")
    groq2 = create_mock_llm("qwen/qwen3.8-27b", provider="groq")

    # M1 fails with daily quota exhaustion
    m1.complete.side_effect = Exception(
        "ResourceExhausted: 429 Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests"
    )
    # Groq 1 succeeds
    groq1.complete.return_value = make_completion_response("Groq GPT-OSS 120B Success")

    pipeline = ResilientFallbackLLM(fallback_chain=[m1, m2, m3, groq1, groq2])
    res = pipeline.complete("test prompt")

    assert res.text == "Groq GPT-OSS 120B Success"
    m1.complete.assert_called_once()
    # M2 and M3 must be SKIPPED completely!
    m2.complete.assert_not_called()
    m3.complete.assert_not_called()
    groq1.complete.assert_called_once()
    groq2.complete.assert_not_called()


def test_groq_model_specific_error_advances_to_next_groq_model():
    """Groq GPT-OSS 120B model-specific error advances to Groq Qwen 3.8 27B."""
    groq1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")
    groq2 = create_mock_llm("qwen/qwen3.8-27b", provider="groq")
    groq3 = create_mock_llm("llama-3.3-70b-versatile", provider="groq")

    groq1.complete.side_effect = Exception("404 NotFound: Model openai/gpt-oss-120b does not exist")
    groq2.complete.return_value = make_completion_response("Qwen 27B Success")

    pipeline = ResilientFallbackLLM(fallback_chain=[groq1, groq2, groq3])
    res = pipeline.complete("test prompt")

    assert res.text == "Qwen 27B Success"
    groq1.complete.assert_called_once()
    groq2.complete.assert_called_once()
    groq3.complete.assert_not_called()


def test_groq_quota_exhaustion_skips_remaining_groq_models_to_ollama():
    """Groq quota exhaustion (429) must skip remaining Groq models and move directly to Ollama."""
    groq1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")
    groq2 = create_mock_llm("qwen/qwen3.8-27b", provider="groq")
    groq3 = create_mock_llm("llama-3.3-70b-versatile", provider="groq")
    ollama = create_mock_llm("llama3.1:8b", provider="ollama")

    groq1.complete.side_effect = Exception("429 rate limit reached for tokens per day on groq")
    ollama.complete.return_value = make_completion_response("Ollama Llama 3.1 8B Success")

    pipeline = ResilientFallbackLLM(fallback_chain=[groq1, groq2, groq3, ollama])
    res = pipeline.complete("test prompt")

    assert res.text == "Ollama Llama 3.1 8B Success"
    groq1.complete.assert_called_once()
    groq2.complete.assert_not_called()
    groq3.complete.assert_not_called()
    ollama.complete.assert_called_once()


def test_seven_model_chain_reaches_ollama_final_fallback():
    """Full 7-model chain: Gemini quota skips to Groq, Groq quota skips to Ollama."""
    g1 = create_mock_llm("gemini-3.8-flash", provider="gemini")
    g2 = create_mock_llm("gemini-3.7-flash", provider="gemini")
    g3 = create_mock_llm("gemini-3.6-flash", provider="gemini")
    q1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")
    q2 = create_mock_llm("qwen/qwen3.8-27b", provider="groq")
    q3 = create_mock_llm("llama-3.3-70b-versatile", provider="groq")
    ol = create_mock_llm("llama3.1:8b", provider="ollama")

    # Gemini hits quota exhaustion on G1
    g1.complete.side_effect = Exception("ResourceExhausted: 429 Quota exceeded (per day)")
    # Groq hits quota exhaustion on Q1
    q1.complete.side_effect = Exception("429 Rate limit exceeded: requests per day limit reached")
    # Ollama succeeds
    ol.complete.return_value = make_completion_response("Offline Llama 3.1 Success")

    pipeline = ResilientFallbackLLM(fallback_chain=[g1, g2, g3, q1, q2, q3, ol])
    res = pipeline.complete("test prompt")

    assert res.text == "Offline Llama 3.1 Success"
    g1.complete.assert_called_once()
    g2.complete.assert_not_called()
    g3.complete.assert_not_called()
    q1.complete.assert_called_once()
    q2.complete.assert_not_called()
    q3.complete.assert_not_called()
    ol.complete.assert_called_once()


@pytest.mark.asyncio
async def test_seven_model_chain_async_streaming_quota_skipping():
    """Async streaming properly skips quota-exhausted providers across the 7-model chain."""
    g1 = create_mock_llm("gemini-3.8-flash", provider="gemini")
    g2 = create_mock_llm("gemini-3.7-flash", provider="gemini")
    g3 = create_mock_llm("gemini-3.6-flash", provider="gemini")
    q1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")

    g1.stream_complete.side_effect = Exception("429 ResourceExhausted: daily quota exceeded")
    q1.astream_complete.return_value = mock_async_stream_generator(["Groq", " Stream", " Token"])

    pipeline = ResilientFallbackLLM(fallback_chain=[g1, g2, g3, q1])

    chunks = []
    async for chunk in pipeline.astream_complete("test streaming prompt"):
        chunks.append(chunk.text)

    assert chunks == ["Groq", " Stream", " Token"]
    g1.stream_complete.assert_called_once()
    g2.stream_complete.assert_not_called()
    g3.stream_complete.assert_not_called()
    q1.astream_complete.assert_called_once()


def test_circuit_breaker_trips_and_skips_provider_on_subsequent_requests():
    """Tripped circuit breaker skips provider immediately (<1ms) on subsequent requests."""
    g1 = create_mock_llm("gemini-3.8-flash", provider="gemini")
    q1 = create_mock_llm("openai/gpt-oss-120b", provider="groq")
    q1.complete.return_value = make_completion_response("Groq Answer")

    # First call: g1 hits daily quota exhaustion
    g1.complete.side_effect = Exception("429 ResourceExhausted: Quota exceeded for metric: per day")

    pipeline = ResilientFallbackLLM(fallback_chain=[g1, q1])
    res1 = pipeline.complete("prompt 1")
    assert res1.text == "Groq Answer"
    assert g1.complete.call_count == 1
    assert is_circuit_open("gemini") is True

    # Second call: circuit breaker is open! g1 must NOT be called at all!
    res2 = pipeline.complete("prompt 2")
    assert res2.text == "Groq Answer"
    assert g1.complete.call_count == 1  # Still 1! Never invoked again!
    assert q1.complete.call_count == 2


