from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

from app.config import (
    GEMINI_API_KEY,
    GEMINI_LLM_MODEL,
    GROQ_API_KEY,
    GROQ_FAST_MODEL,
    GROQ_LLM_MODEL,
    LLM_FALLBACK_CHAIN_STR,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_LLM_MODEL,
    USE_FAST_LLM,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SUPPORTED_PROVIDERS: Set[str] = {"gemini", "groq", "ollama"}
_client_cache: Dict[Tuple[str, str], Any] = {}


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_name: str


def _normalize_provider(provider: str) -> str:
    return (provider or "").strip().lower()


def _default_model_for_provider(provider: str, *, use_fast_choice: bool = False) -> str:
    if provider == "gemini":
        return GEMINI_LLM_MODEL
    if provider == "groq":
        return GROQ_FAST_MODEL if use_fast_choice else GROQ_LLM_MODEL
    if provider == "ollama":
        return OLLAMA_LLM_MODEL
    return ""


def is_provider_available(provider: str) -> bool:
    provider = _normalize_provider(provider)
    if provider == "gemini":
        return bool(GEMINI_API_KEY)
    if provider == "groq":
        return bool(GROQ_API_KEY)
    if provider == "ollama":
        # Local provider does not require API key. Runtime connectivity is handled at call time.
        return True
    return False


def _parse_fallback_chain() -> List[ModelSpec]:
    specs: List[ModelSpec] = []
    for item in LLM_FALLBACK_CHAIN_STR.split(","):
        raw = item.strip()
        if not raw or ":" not in raw:
            continue

        provider, model_name = raw.split(":", 1)
        provider = _normalize_provider(provider)
        model_name = (model_name or "").strip()
        if not provider or not model_name:
            continue
        if provider not in _SUPPORTED_PROVIDERS:
            logger.warning("Skipping unsupported provider in fallback chain: %s", provider)
            continue

        specs.append(ModelSpec(provider=provider, model_name=model_name))
    return specs


def _dedupe_specs(specs: List[ModelSpec]) -> List[ModelSpec]:
    out: List[ModelSpec] = []
    seen: Set[Tuple[str, str]] = set()
    for spec in specs:
        key = (spec.provider, spec.model_name)
        if key in seen:
            continue
        seen.add(key)
        out.append(spec)
    return out


def _build_primary_spec() -> ModelSpec:
    raw = _normalize_provider(LLM_PROVIDER)
    if raw not in _SUPPORTED_PROVIDERS:
        logger.warning("Unsupported LLM_PROVIDER '%s'. Falling back to gemini.", raw)
        raw = "gemini"

    if USE_FAST_LLM and raw != "ollama":
        provider = "groq"
        model_name = _default_model_for_provider("groq", use_fast_choice=True)
    else:
        provider = raw
        model_name = _default_model_for_provider(provider, use_fast_choice=False)

    return ModelSpec(provider=provider, model_name=model_name)


def get_available_model_specs() -> List[ModelSpec]:
    ordered: List[ModelSpec] = []

    primary = _build_primary_spec()
    ordered.append(primary)
    ordered.extend(_parse_fallback_chain())

    # Ensure each known provider still gets a default attempt if available.
    ordered.extend([
        ModelSpec(provider="gemini", model_name=_default_model_for_provider("gemini")),
        ModelSpec(provider="groq", model_name=_default_model_for_provider("groq")),
        ModelSpec(provider="ollama", model_name=_default_model_for_provider("ollama")),
    ])

    deduped = _dedupe_specs(ordered)
    available = [spec for spec in deduped if is_provider_available(spec.provider)]

    if not available:
        logger.error("No LLM providers are available after configuration filtering.")

    return available


def reset_client_cache() -> None:
    """Clear cached LLM client instances for test isolation."""
    _client_cache.clear()


def create_llm_client(spec: ModelSpec) -> Any:
    cache_key = (spec.provider, spec.model_name)
    if cache_key in _client_cache:
        return _client_cache[cache_key]

    provider = _normalize_provider(spec.provider)

    if provider == "gemini":
        from llama_index.llms.gemini import Gemini
        import google.generativeai as genai

        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured.")

        model_name = spec.model_name
        sdk_model_name = model_name if model_name.startswith("models/") else f"models/{model_name}"

        # Safe initialization wrapper: if genai.get_model() raises during client
        # creation because a model identifier is not yet registered or network is unreachable,
        # provide a fallback metadata mock so the client instance can still be initialized
        # and executed at runtime to trigger real API response/fallback behavior.
        orig_get_model = getattr(genai, "get_model", None)
        try:
            from unittest.mock import MagicMock
            mock_meta = MagicMock()
            mock_meta.supported_generation_methods = ["generateContent"]
            mock_meta.output_token_limit = 8192

            def _safe_get_model(name):
                try:
                    return orig_get_model(name)
                except Exception:
                    return mock_meta

            genai.get_model = _safe_get_model
            client = Gemini(
                model=sdk_model_name,
                api_key=GEMINI_API_KEY,
                temperature=0.2,
                max_tokens=4096,
            )
        finally:
            if orig_get_model:
                genai.get_model = orig_get_model

    elif provider == "groq":
        from llama_index.llms.groq import Groq

        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")

        model_lower = spec.model_name.lower()
        if "gpt-oss-120b" in model_lower or "minimax" in model_lower or "70b" in model_lower:
            ctx = 131072
        elif "qwen" in model_lower:
            ctx = 32768
        else:
            ctx = 32768

        client = Groq(
            model=spec.model_name,
            api_key=GROQ_API_KEY,
            context_window=ctx,
            max_tokens=4096,
            temperature=0.2,
        )
    elif provider == "ollama":
        from llama_index.llms.ollama import Ollama

        client = Ollama(
            model=spec.model_name,
            base_url=OLLAMA_BASE_URL,
            request_timeout=120.0,
            context_window=16384,
            additional_kwargs={"options": {"num_ctx": 16384}},
        )
    else:
        raise ValueError(f"Unsupported provider: {spec.provider}")

    # Keep provider/model metadata on the client instance for telemetry.
    setattr(client, "_cb_provider", provider)
    setattr(client, "_cb_model_name", spec.model_name)

    _client_cache[cache_key] = client
    return client

