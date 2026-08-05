import re
import asyncio
import logging
import time
import threading
import inspect
from typing import Any, List, Optional, AsyncGenerator
from pydantic import Field

from llama_index.core.llms import CustomLLM, CompletionResponse, CompletionResponseGen, LLMMetadata
from app.config import (
    LLM_FALLBACK_RETRY_THRESHOLD,
)
from app.services.model_manager import (
    create_llm_client,
    get_available_model_specs,
)

logger = logging.getLogger(__name__)

_last_llm_usage_lock = threading.Lock()
_last_llm_usage: dict = {"provider": None, "model": None}


def _record_llm_usage(provider: str, model_name: str) -> None:
    with _last_llm_usage_lock:
        _last_llm_usage["provider"] = provider
        _last_llm_usage["model"] = model_name


def get_last_llm_usage() -> dict:
    with _last_llm_usage_lock:
        return {
            "provider": _last_llm_usage.get("provider"),
            "model": _last_llm_usage.get("model"),
        }


def reset_last_llm_usage() -> None:
    with _last_llm_usage_lock:
        _last_llm_usage["provider"] = None
        _last_llm_usage["model"] = None


def _sleep_safe(seconds: float) -> None:
    """Sleep without blocking the asyncio event loop.

    When called from a synchronous function that is already running inside a
    thread-pool executor (i.e. there is a running event loop on another thread),
    ``time.sleep`` is perfectly safe because it only blocks the *worker* thread,
    not the event loop.  When there is *no* running event loop (pure sync
    context) ``time.sleep`` is equally safe.

    The previous pattern of using bare ``time.sleep`` was flagged as a
    blocking-call-in-async-context risk because ``ResilientFallbackLLM.complete``
    and ``stream_complete`` could in theory be invoked directly on the event
    loop thread.  This helper makes the intent explicit and documents the
    contract: sync methods MUST be called via ``loop.run_in_executor``, never
    directly from async code.
    """
    try:
        asyncio.get_running_loop()
        # A running event loop exists — we are on the event loop thread.
        # Blocking here would stall all async tasks.  Skip the wait; the
        # retry-after delay is small (≤ LLM_FALLBACK_RETRY_THRESHOLD seconds)
        # and falling through to the next model is safer than freezing the app.
        logger.warning(
            "Skipping retry-after sleep in sync method called on event-loop thread. "
            "Use acomplete() / astream_complete() from async contexts."
        )
    except RuntimeError:
        # No running event loop → pure sync context, safe to block.
        time.sleep(seconds)

class AllModelsExhaustedError(Exception):
    """Exception raised when all fallback LLMs in the chain fail."""
    def __init__(self, message: str, errors: dict):
        super().__init__(message)
        self.errors = errors

def is_rate_limit_or_quota_error(err: Exception) -> bool:
    """Check if the exception is a rate limit or quota exceeded error (HTTP 429)."""
    msg = str(err).lower()
    if "resourceexhausted" in type(err).__name__.lower():
        return True
    if hasattr(err, "status_code") and getattr(err, "status_code") == 429:
        return True
    return (
        "rate limit" in msg
        or "rate_limit" in msg
        or "too many requests" in msg
        or "429" in msg
        or "quota" in msg
        or "resource exhausted" in msg
        or "exhausted" in msg
    )

def parse_retry_delay(err: Exception) -> Optional[int]:
    """Parse retry delay in seconds from Gemini/Groq error messages."""
    msg = str(err)
    # Gemini protobuf string retry_delay: "retry_delay { seconds: N }"
    gemini_match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", msg, re.IGNORECASE)
    if gemini_match:
        return int(gemini_match.group(1))

    # Groq string retry_delay: "Please try again in Xs."
    groq_match = re.search(r"try\s+again\s+in\s+(\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
    if groq_match:
        return int(float(groq_match.group(1)))

    generic_match = re.search(r"retry\s+after\s+(\d+)", msg, re.IGNORECASE)
    if generic_match:
        return int(generic_match.group(1))

    return None

def _provider_and_model(llm: Any) -> tuple[str, str]:
    provider = getattr(llm, "_cb_provider", type(llm).__name__)
    model_name = getattr(llm, "_cb_model_name", getattr(llm, "model", getattr(llm, "model_name", "unknown")))
    return str(provider), str(model_name)

class ResilientFallbackLLM(CustomLLM):
    """LlamaIndex-compliant LLM class supporting fallback chain across models and providers."""
    fallback_chain: List[Any] = Field(description="Active LLM instances in fallback priority order")

    @property
    def metadata(self) -> LLMMetadata:
        return self.fallback_chain[0].metadata

    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        errors = {}
        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)
            
            # Allow up to 1 retry attempt if retry-after delay is small
            retries = 1
            for attempt in range(retries + 1):
                try:
                    logger.info(f"Attempting completion with {provider}/{model_name} (attempt {attempt + 1})...")
                    response = llm.complete(prompt, **kwargs)
                    _record_llm_usage(provider, model_name)
                    logger.info(f"Completion succeeded with {provider}/{model_name}.")
                    return response
                except Exception as e:
                    if not is_rate_limit_or_quota_error(e):
                        logger.warning(
                            f"Non-rate-limit error on {provider}/{model_name}. Trying next fallback model: {e}"
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break
                    
                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited. "
                            f"Short retry delay detected: {delay}s. Waiting and retrying..."
                        )
                        _sleep_safe(delay)
                        continue
                    
                    logger.warning(
                        f"Model {provider}/{model_name} rate limited. Moving to fallback."
                    )
                    errors[f"{provider}/{model_name}"] = str(e)
                    break
        
        raise AllModelsExhaustedError(
            "All LLM models in the fallback chain were exhausted.",
            errors=errors
        )

    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        def gen():
            errors = {}
            for llm in self.fallback_chain:
                provider, model_name = _provider_and_model(llm)
                
                retries = 1
                for attempt in range(retries + 1):
                    tokens_yielded = False
                    try:
                        logger.info(f"Attempting streaming completion with {provider}/{model_name} (attempt {attempt + 1})...")
                        stream_response = llm.stream_complete(prompt, **kwargs)
                        for chunk in stream_response:
                            if not tokens_yielded:
                                _record_llm_usage(provider, model_name)
                            tokens_yielded = True
                            yield chunk
                        logger.info(f"Streaming completion succeeded with {provider}/{model_name}.")
                        return
                    except Exception as e:
                        if tokens_yielded:
                            logger.error(f"Error on {provider}/{model_name} (bypass fallback): {e}")
                            raise e

                        if not is_rate_limit_or_quota_error(e):
                            logger.warning(
                                f"Stream startup error on {provider}/{model_name}. "
                                f"Trying next fallback model: {e}"
                            )
                            errors[f"{provider}/{model_name}"] = str(e)
                            break
                        
                        delay = parse_retry_delay(e)
                        if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                            logger.warning(
                                f"Model {provider}/{model_name} rate limited. "
                                f"Short retry delay detected: {delay}s. Waiting and retrying..."
                            )
                            _sleep_safe(delay)
                            continue
                        
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited. Moving to fallback."
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break
            
            raise AllModelsExhaustedError(
                "All LLM models in the fallback chain were exhausted.",
                errors=errors
            )

        return gen()

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        errors = {}
        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)
            
            retries = 1
            for attempt in range(retries + 1):
                try:
                    logger.info(f"Attempting async completion with {provider}/{model_name} (attempt {attempt + 1})...")
                    response = await llm.acomplete(prompt, **kwargs)
                    _record_llm_usage(provider, model_name)
                    logger.info(f"Async completion succeeded with {provider}/{model_name}.")
                    return response
                except Exception as e:
                    if not is_rate_limit_or_quota_error(e):
                        logger.warning(
                            f"Non-rate-limit error on {provider}/{model_name}. Trying next fallback model: {e}"
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break
                    
                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited. "
                            f"Short retry delay detected: {delay}s. Waiting and retrying..."
                        )
                        await asyncio.sleep(delay)
                        continue
                    
                    logger.warning(
                        f"Model {provider}/{model_name} rate limited. Moving to fallback."
                    )
                    errors[f"{provider}/{model_name}"] = str(e)
                    break
        
        raise AllModelsExhaustedError(
            "All LLM models in the fallback chain were exhausted.",
            errors=errors
        )

    async def astream_complete(self, prompt: str, **kwargs: Any) -> AsyncGenerator[Any, None]:
        errors = {}
        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)

            retries = 1
            for attempt in range(retries + 1):
                tokens_yielded = False
                try:
                    logger.info(f"Attempting async streaming completion with {provider}/{model_name} (attempt {attempt + 1})...")
                    stream_response = llm.astream_complete(prompt, **kwargs)
                    if inspect.isawaitable(stream_response):
                        stream_response = await stream_response
                    if not hasattr(stream_response, "__aiter__"):
                        raise TypeError(
                            f"{provider}/{model_name} returned non-async stream: "
                            f"{type(stream_response).__name__}"
                        )

                    async for chunk in stream_response:
                        if not tokens_yielded:
                            _record_llm_usage(provider, model_name)
                        tokens_yielded = True
                        yield chunk
                    logger.info(f"Async streaming completion succeeded with {provider}/{model_name}.")
                    return
                except Exception as e:
                    if tokens_yielded:
                        logger.error(f"Error on {provider}/{model_name} (bypass fallback): {e}")
                        raise e

                    if not is_rate_limit_or_quota_error(e):
                        logger.warning(
                            f"Async stream startup error on {provider}/{model_name}. "
                            f"Trying next fallback model: {e}"
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited. "
                            f"Short retry delay detected: {delay}s. Waiting and retrying..."
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.warning(
                        f"Model {provider}/{model_name} rate limited. Moving to fallback."
                    )
                    errors[f"{provider}/{model_name}"] = str(e)
                    break

        raise AllModelsExhaustedError(
            "All LLM models in the fallback chain were exhausted.",
            errors=errors
        )

_resilient_llm_instance = None

def get_resilient_llm() -> ResilientFallbackLLM:
    """Build or retrieve singleton ResilientFallbackLLM instance."""
    global _resilient_llm_instance
    if _resilient_llm_instance is None:
        chain = []
        for spec in get_available_model_specs():
            try:
                llm = create_llm_client(spec)
                chain.append(llm)
            except Exception as e:
                logger.warning(f"Could not pre-initialize {spec.provider}/{spec.model_name}: {e}")
        
        if not chain:
            raise RuntimeError("No fallback LLM clients could be initialized.")
        _resilient_llm_instance = ResilientFallbackLLM(fallback_chain=chain)
    return _resilient_llm_instance

async def generate_with_fallback(prompt: str, **kwargs: Any) -> str:
    """Exposes a clean async function interface to perform LLM generation with fallbacks."""
    llm = get_resilient_llm()
    response = await llm.acomplete(prompt, **kwargs)
    return str(response).strip()

async def stream_with_fallback(prompt: str, **kwargs: Any) -> AsyncGenerator[Any, None]:
    """Exposes a clean streaming function interface returning an async generator of completion chunks."""
    llm = get_resilient_llm()
    stream_response = llm.astream_complete(prompt, **kwargs)
    if inspect.isawaitable(stream_response):
        stream_response = await stream_response
    async for chunk in stream_response:
        yield chunk
