import re
import asyncio
import logging
import time
import threading
import inspect
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Set, AsyncGenerator
from pydantic import Field

from llama_index.core.llms import CustomLLM, CompletionResponse, CompletionResponseGen, LLMMetadata
from app import config
from app.config import (
    LLM_FALLBACK_RETRY_THRESHOLD,
    ALLOW_CROSS_PROVIDER_FALLBACK,
)
from app.services.model_manager import (
    create_llm_client,
    get_available_model_specs,
)

logger = logging.getLogger(__name__)

_STREAM_BRIDGE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="llm-sync-stream")

import contextvars

_last_llm_usage_var: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "last_llm_usage", default={"provider": None, "model": None}
)


def _record_llm_usage(provider: str, model_name: str) -> None:
    _last_llm_usage_var.set({"provider": provider, "model": model_name})


def get_last_llm_usage() -> dict:
    return _last_llm_usage_var.get()


def reset_last_llm_usage() -> None:
    _last_llm_usage_var.set({"provider": None, "model": None})


# ─── Circuit Breaker & Quota Handling ─────────────────────────────────────────

_CIRCUIT_BREAKER_STATE: Dict[str, float] = {}  # provider -> cooldown_until timestamp
_cb_lock = threading.Lock()


def record_quota_exhaustion(provider: str, delay: Optional[int] = None) -> None:
    """Trip circuit breaker for a provider whose quota is exhausted."""
    provider_norm = (provider or "").strip().lower()
    cooldown = min(max(float(delay), 10.0), 3600.0) if (delay is not None and delay > 0) else 60.0
    with _cb_lock:
        _CIRCUIT_BREAKER_STATE[provider_norm] = time.time() + cooldown
    logger.warning(
        f"Circuit breaker tripped for provider '{provider_norm}': quota exhausted. Cooling down for {cooldown:.1f}s."
    )


def is_circuit_open(provider: str) -> bool:
    """Return True if provider circuit breaker is open (cooling down from previous quota exhaustion)."""
    provider_norm = (provider or "").strip().lower()
    with _cb_lock:
        cooldown_until = _CIRCUIT_BREAKER_STATE.get(provider_norm)
        if cooldown_until is None:
            return False
        if time.time() < cooldown_until:
            return True
        del _CIRCUIT_BREAKER_STATE[provider_norm]
        logger.info(f"Circuit breaker reset for provider '{provider_norm}' (cooldown period expired).")
        return False


def clear_circuit_breaker(provider: str) -> None:
    """Clear open circuit upon confirmed provider success."""
    provider_norm = (provider or "").strip().lower()
    with _cb_lock:
        _CIRCUIT_BREAKER_STATE.pop(provider_norm, None)


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (for test fixtures)."""
    with _cb_lock:
        _CIRCUIT_BREAKER_STATE.clear()


def is_daily_quota_exhausted(err: Exception) -> bool:
    """Check if the exception indicates daily or long-duration quota exhaustion."""
    msg = str(err).lower()
    if (
        "per day" in msg
        or "requests per day" in msg
        or "tokens per day" in msg
        or "free_tier_requests" in msg
        or "generate_content_free_tier" in msg
        or "limit: 20" in msg
        or "exceeded your current quota" in msg
    ):
        return True
    delay = parse_retry_delay(err)
    if delay is not None and delay > 600:
        return True
    return False


def is_provider_quota_exhausted(err: Exception) -> bool:
    """Check if the exception indicates a genuine project-level / provider-level quota exhaustion."""
    msg = str(err).lower()
    err_type = type(err).__name__.lower()

    if "resourceexhausted" in err_type and (
        "quota" in msg or "exhausted" in msg or "free_tier" in msg or "limit" in msg
    ):
        return True

    quota_indicators = (
        "quota exceeded",
        "quota_exceeded",
        "resource exhausted",
        "resource_exhausted",
        "daily quota",
        "daily limit",
        "per day",
        "requests per day",
        "tokens per day",
        "free_tier_requests",
        "generate_content_free_tier",
        "exceeded your current quota",
    )
    return any(ind in msg for ind in quota_indicators)


def is_non_retryable_error(err: Exception) -> bool:
    """Check if the exception is permanent/non-retryable for the current model."""
    msg = str(err).lower()
    err_type = type(err).__name__.lower()

    if (
        "notfound" in err_type
        or "not_found" in msg
        or "404" in msg
        or "is not found" in msg
        or "does not exist" in msg
        or "unsupported model" in msg
    ):
        return True
    if (
        "unauthenticated" in err_type
        or "permissiondenied" in err_type
        or "invalid_api_key" in msg
        or "api key not valid" in msg
        or "401" in msg
        or "403" in msg
    ):
        return True
    if "invalidargument" in err_type or "bad request" in msg or "400" in msg:
        return True
    return False


def is_rate_limit_or_quota_error(err: Exception) -> bool:
    """Backward compatibility check for rate limit or quota exceeded error."""
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


def _sleep_safe(seconds: float) -> None:
    """Sleep without blocking the asyncio event loop."""
    try:
        asyncio.get_running_loop()
        logger.warning(
            "Skipping retry-after sleep in sync method called on event-loop thread. "
            "Use acomplete() / astream_complete() from async contexts."
        )
    except RuntimeError:
        time.sleep(max(0.0, float(seconds)))


class AllModelsExhaustedError(Exception):
    """Exception raised when all fallback LLMs in the chain fail."""
    def __init__(self, message: str, errors: dict):
        super().__init__(message)
        self.errors = errors


def _provider_and_model(llm: Any) -> tuple[str, str]:
    provider = getattr(llm, "_cb_provider", type(llm).__name__)
    model_name = getattr(llm, "_cb_model_name", getattr(llm, "model", getattr(llm, "model_name", "unknown")))
    return str(provider), str(model_name)


_STREAM_END = object()


def _next_chunk_or_end(stream_iter):
    try:
        return next(stream_iter)
    except StopIteration:
        return _STREAM_END


async def _bridge_sync_stream_complete(llm: Any, prompt: str, **kwargs: Any) -> AsyncGenerator[Any, None]:
    """Bridge sync stream_complete() to async iteration without blocking event loop."""
    loop = asyncio.get_running_loop()
    stream_iter = await loop.run_in_executor(
        _STREAM_BRIDGE_EXECUTOR,
        partial(llm.stream_complete, prompt, **kwargs)
    )
    while True:
        chunk = await loop.run_in_executor(
            _STREAM_BRIDGE_EXECUTOR,
            partial(_next_chunk_or_end, stream_iter)
        )
        if chunk is _STREAM_END:
            break
        yield chunk


class ResilientFallbackLLM(CustomLLM):
    """
    Custom LLM that executes a chain of LLM models with automatic fallback.
    Supports provider-level circuit breaking, retry with delay, and cross-provider privacy enforcement.
    """
    fallback_chain: List[Any] = Field(default_factory=list)

    @property
    def metadata(self) -> LLMMetadata:
        if self.fallback_chain:
            return self.fallback_chain[0].metadata
        return LLMMetadata(context_window=32768, num_output=4096, model_name="resilient_fallback")

    def _is_cross_provider_blocked(self, primary_provider: Optional[str], candidate_provider: str) -> bool:
        """Check if fallback to candidate_provider violates cross-provider privacy policy."""
        if not primary_provider:
            return False
        if candidate_provider == primary_provider:
            return False
        # Fallback to local on-device Ollama is permitted (no external data transmission)
        if candidate_provider == "ollama":
            return False
        # External cross-provider cloud fallback requires explicit opt-in
        allow_cross = getattr(config, "ALLOW_CROSS_PROVIDER_FALLBACK", False)
        return not allow_cross

    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        errors = {}
        skipped_providers: Set[str] = set()
        primary_provider: Optional[str] = None

        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)
            provider_norm = provider.strip().lower()

            if primary_provider is None:
                primary_provider = provider_norm

            if provider_norm in skipped_providers:
                continue

            if is_circuit_open(provider_norm):
                logger.info(f"Circuit breaker open for provider '{provider_norm}'. Skipping model {model_name}.")
                continue

            if self._is_cross_provider_blocked(primary_provider, provider_norm):
                logger.info(
                    "Cross-provider fallback from '%s' to '%s' blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False).",
                    primary_provider,
                    provider_norm,
                )
                errors[f"{provider}/{model_name}"] = "Cross-provider fallback blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False)"
                continue

            for attempt in range(2):
                try:
                    logger.debug(f"Attempting completion with {provider}/{model_name} (attempt {attempt+1})...")
                    res = llm.complete(prompt, **kwargs)
                    _record_llm_usage(provider, model_name)
                    clear_circuit_breaker(provider_norm)
                    logger.info(f"Completion succeeded with {provider}/{model_name}.")
                    return res
                except Exception as e:
                    if is_provider_quota_exhausted(e):
                        delay = parse_retry_delay(e)
                        is_daily = is_daily_quota_exhausted(e)
                        if not is_daily and delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                            logger.warning(
                                f"Model {provider}/{model_name} short rate limit ({delay}s). Retrying once."
                            )
                            _sleep_safe(delay)
                            continue

                        logger.warning(
                            f"Provider '{provider}' quota exhausted on {model_name}: {e}. "
                            f"Skipping remaining models for provider '{provider}'."
                        )
                        skipped_providers.add(provider_norm)
                        record_quota_exhaustion(provider_norm, delay)
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    if is_non_retryable_error(e):
                        logger.warning(
                            f"Model-specific error on {provider}/{model_name}: {e}. Trying next fallback model."
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited ({delay}s). Retrying once."
                        )
                        _sleep_safe(delay)
                        continue

                    logger.warning(f"Model {provider}/{model_name} error: {e}. Moving to fallback.")
                    errors[f"{provider}/{model_name}"] = str(e)
                    break

        raise AllModelsExhaustedError(
            "All LLM models in the fallback chain were exhausted.",
            errors=errors
        )

    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        errors = {}
        skipped_providers: Set[str] = set()
        primary_provider: Optional[str] = None

        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)
            provider_norm = provider.strip().lower()

            if primary_provider is None:
                primary_provider = provider_norm

            if provider_norm in skipped_providers:
                continue

            if is_circuit_open(provider_norm):
                logger.info(f"Circuit breaker open for provider '{provider_norm}'. Skipping model {model_name}.")
                continue

            if self._is_cross_provider_blocked(primary_provider, provider_norm):
                logger.info(
                    "Cross-provider fallback from '%s' to '%s' blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False).",
                    primary_provider,
                    provider_norm,
                )
                errors[f"{provider}/{model_name}"] = "Cross-provider fallback blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False)"
                continue

            for attempt in range(2):
                try:
                    logger.debug(f"Attempting async completion with {provider}/{model_name} (attempt {attempt+1})...")
                    if hasattr(llm, "acomplete"):
                        res = await llm.acomplete(prompt, **kwargs)
                    else:
                        loop = asyncio.get_running_loop()
                        res = await loop.run_in_executor(None, partial(llm.complete, prompt, **kwargs))
                    _record_llm_usage(provider, model_name)
                    clear_circuit_breaker(provider_norm)
                    logger.info(f"Async completion succeeded with {provider}/{model_name}.")
                    return res
                except Exception as e:
                    if is_provider_quota_exhausted(e):
                        delay = parse_retry_delay(e)
                        is_daily = is_daily_quota_exhausted(e)
                        if not is_daily and delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                            logger.warning(
                                f"Model {provider}/{model_name} short rate limit ({delay}s). Retrying once."
                            )
                            await asyncio.sleep(delay)
                            continue

                        logger.warning(
                            f"Provider '{provider}' quota exhausted on {model_name}: {e}. "
                            f"Skipping remaining models for provider '{provider}'."
                        )
                        skipped_providers.add(provider_norm)
                        record_quota_exhaustion(provider_norm, delay)
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    if is_non_retryable_error(e):
                        logger.warning(
                            f"Model-specific error on {provider}/{model_name}: {e}. Trying next fallback model."
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited ({delay}s). Retrying once."
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.warning(f"Model {provider}/{model_name} async error: {e}. Moving to fallback.")
                    errors[f"{provider}/{model_name}"] = str(e)
                    break

        raise AllModelsExhaustedError(
            "All LLM models in the fallback chain were exhausted.",
            errors=errors
        )

    def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
        errors = {}
        skipped_providers: Set[str] = set()
        primary_provider: Optional[str] = None

        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)
            provider_norm = provider.strip().lower()

            if primary_provider is None:
                primary_provider = provider_norm

            if provider_norm in skipped_providers:
                continue

            if is_circuit_open(provider_norm):
                logger.info(f"Circuit breaker open for provider '{provider_norm}'. Skipping model {model_name}.")
                continue

            if self._is_cross_provider_blocked(primary_provider, provider_norm):
                logger.info(
                    "Cross-provider fallback from '%s' to '%s' blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False).",
                    primary_provider,
                    provider_norm,
                )
                errors[f"{provider}/{model_name}"] = "Cross-provider fallback blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False)"
                continue

            for attempt in range(2):
                tokens_yielded = False
                try:
                    logger.debug(f"Attempting streaming completion with {provider}/{model_name} (attempt {attempt+1})...")
                    stream_res = llm.stream_complete(prompt, **kwargs)
                    for chunk in stream_res:
                        if not tokens_yielded:
                            _record_llm_usage(provider, model_name)
                            clear_circuit_breaker(provider_norm)
                        tokens_yielded = True
                        yield chunk
                    logger.info(f"Streaming completion succeeded with {provider}/{model_name}.")
                    return
                except Exception as e:
                    if tokens_yielded:
                        logger.error(f"Error on {provider}/{model_name} mid-stream (bypass fallback): {e}")
                        raise e

                    if is_provider_quota_exhausted(e):
                        delay = parse_retry_delay(e)
                        is_daily = is_daily_quota_exhausted(e)
                        if not is_daily and delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                            logger.warning(
                                f"Model {provider}/{model_name} short rate limit ({delay}s). Retrying once."
                            )
                            _sleep_safe(delay)
                            continue

                        logger.warning(
                            f"Provider '{provider}' quota exhausted on {model_name}: {e}. "
                            f"Skipping remaining models for provider '{provider}'."
                        )
                        skipped_providers.add(provider_norm)
                        record_quota_exhaustion(provider_norm, delay)
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    if is_non_retryable_error(e):
                        logger.warning(
                            f"Stream startup model-specific error on {provider}/{model_name}: {e}. Trying next fallback model."
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited ({delay}s). Retrying once."
                        )
                        _sleep_safe(delay)
                        continue

                    logger.warning(f"Model {provider}/{model_name} stream error: {e}. Moving to fallback.")
                    errors[f"{provider}/{model_name}"] = str(e)
                    break

        raise AllModelsExhaustedError(
            "All LLM models in the fallback chain were exhausted.",
            errors=errors
        )

    async def astream_complete(self, prompt: str, **kwargs: Any) -> AsyncGenerator[CompletionResponse, None]:
        errors = {}
        skipped_providers: Set[str] = set()
        primary_provider: Optional[str] = None

        for llm in self.fallback_chain:
            provider, model_name = _provider_and_model(llm)
            provider_norm = provider.strip().lower()

            if primary_provider is None:
                primary_provider = provider_norm

            if provider_norm in skipped_providers:
                continue

            if is_circuit_open(provider_norm):
                logger.info(f"Circuit breaker open for provider '{provider_norm}'. Skipping model {model_name}.")
                continue

            if self._is_cross_provider_blocked(primary_provider, provider_norm):
                logger.info(
                    "Cross-provider fallback from '%s' to '%s' blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False).",
                    primary_provider,
                    provider_norm,
                )
                errors[f"{provider}/{model_name}"] = "Cross-provider fallback blocked by privacy policy (ALLOW_CROSS_PROVIDER_FALLBACK=False)"
                continue

            for attempt in range(2):
                tokens_yielded = False
                try:
                    logger.debug(f"Attempting async streaming completion with {provider}/{model_name} (attempt {attempt+1})...")
                    if provider_norm == "gemini":
                        # Gemini async stream path can emit a startup validation error
                        # (LLMCompletionEndEvent expecting CompletionResponse). Use
                        # sync streaming bridged via executor for reliability.
                        stream_response = _bridge_sync_stream_complete(llm, prompt, **kwargs)
                    else:
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
                            clear_circuit_breaker(provider_norm)
                        tokens_yielded = True
                        yield chunk

                    logger.info(f"Async streaming completion succeeded with {provider}/{model_name}.")
                    return
                except Exception as e:
                    if tokens_yielded:
                        logger.error(f"Error on {provider}/{model_name} mid-stream (bypass fallback): {e}")
                        raise e

                    if is_provider_quota_exhausted(e):
                        delay = parse_retry_delay(e)
                        is_daily = is_daily_quota_exhausted(e)
                        if not is_daily and delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                            logger.warning(
                                f"Model {provider}/{model_name} short rate limit ({delay}s). Retrying once."
                            )
                            await asyncio.sleep(delay)
                            continue

                        logger.warning(
                            f"Provider '{provider}' quota exhausted on {model_name}: {e}. "
                            f"Skipping remaining models for provider '{provider}'."
                        )
                        skipped_providers.add(provider_norm)
                        record_quota_exhaustion(provider_norm, delay)
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    if is_non_retryable_error(e):
                        logger.warning(
                            f"Async stream startup model-specific error on {provider}/{model_name}: {e}. Trying next fallback model."
                        )
                        errors[f"{provider}/{model_name}"] = str(e)
                        break

                    delay = parse_retry_delay(e)
                    if delay is not None and delay <= LLM_FALLBACK_RETRY_THRESHOLD and attempt == 0:
                        logger.warning(
                            f"Model {provider}/{model_name} rate limited ({delay}s). Retrying once."
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.warning(f"Model {provider}/{model_name} async stream error: {e}. Moving to fallback.")
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
        logger.info("Initializing resilient fallback LLM chain.")
        chain = []
        for spec in get_available_model_specs():
            try:
                llm = create_llm_client(spec)
                chain.append(llm)
                logger.info(f"Added fallback model: {spec.provider}/{spec.model_name}")
            except Exception as e:
                logger.warning(f"Could not pre-initialize {spec.provider}/{spec.model_name}: {e}")

        if not chain:
            raise RuntimeError("No fallback LLM clients could be initialized.")
        _resilient_llm_instance = ResilientFallbackLLM(fallback_chain=chain)
        logger.info(f"Fallback chain initialized with {len(chain)} model(s).")
    return _resilient_llm_instance


def reset_resilient_llm() -> None:
    """Reset singleton ResilientFallbackLLM instance and circuit breakers for test isolation."""
    global _resilient_llm_instance
    _resilient_llm_instance = None
    reset_circuit_breakers()


async def generate_with_fallback(prompt: str, **kwargs: Any) -> str:
    """Exposes a clean async function interface to perform LLM generation with fallbacks."""
    logger.info("generate_with_fallback started.")
    llm = get_resilient_llm()
    response = await llm.acomplete(prompt, **kwargs)
    logger.info("generate_with_fallback completed.")
    return str(response).strip()


async def stream_with_fallback(prompt: str, **kwargs: Any) -> AsyncGenerator[Any, None]:
    """Exposes a clean streaming function interface returning an async generator of completion chunks."""
    logger.info("stream_with_fallback started.")
    llm = get_resilient_llm()
    stream_response = llm.astream_complete(prompt, **kwargs)
    if inspect.isawaitable(stream_response):
        stream_response = await stream_response
    async for chunk in stream_response:
        yield chunk
