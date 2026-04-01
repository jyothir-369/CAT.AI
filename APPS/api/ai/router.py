from core.config import settings
from core.exceptions import AllProvidersFailedError
from ai.circuit_breaker import get_breaker
from ai.providers.base import BaseProvider
from ai.providers.openai import OpenAIProvider
from ai.providers.anthropic import AnthropicProvider
from ai.providers.groq import GroqProvider
from ai.providers.gemini import GeminiProvider
from ai.providers.vllm import VLLMProvider

# Singleton provider instances
_providers: dict[str, BaseProvider] = {
    "openai":    OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "groq":      GroqProvider(),
    "gemini":    GeminiProvider(),
    "vllm":      VLLMProvider(),
}

# Failover order
FAILOVER_ORDER = ["openai", "anthropic", "groq"]

# Models that support tool/function calling
TOOL_CAPABLE_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
    "claude-opus-4-6", "claude-sonnet-4-6",
}

# Cheap/fast models for background tasks (summarisation, memory extraction)
CHEAP_MODELS = {
    "groq": "llama3-70b-8192",
    "openai": "gpt-4o-mini",
}


def get_provider(name: str) -> BaseProvider:
    return _providers[name]


def route(
    requested_model: str | None = None,
    workspace_default: str | None = None,
    needs_tools: bool = False,
    long_context: bool = False,
    cost_optimise: bool = False,
) -> tuple[BaseProvider, str]:
    """
    Returns (provider, model_id) based on routing signals.
    Falls back through FAILOVER_ORDER if the primary provider's circuit is open.
    """
    # 1. Explicit user selection takes precedence
    if requested_model:
        provider_name, model = _resolve_model(requested_model)
        breaker = get_breaker(provider_name)
        if breaker.is_available():
            return _providers[provider_name], model
        # Fall through to routing logic if primary is down

    # 2. Long context → Gemini 1.5 Pro
    if long_context:
        if get_breaker("gemini").is_available():
            return _providers["gemini"], "gemini-1.5-pro"

    # 3. Tool calling required → must use capable model
    if needs_tools:
        for provider_name in ["openai", "anthropic"]:
            if get_breaker(provider_name).is_available():
                model = "gpt-4o" if provider_name == "openai" else "claude-sonnet-4-6"
                return _providers[provider_name], model

    # 4. Cost optimise → Groq
    if cost_optimise:
        if get_breaker("groq").is_available():
            return _providers["groq"], CHEAP_MODELS["groq"]

    # 5. Workspace default or global default
    default = workspace_default or settings.DEFAULT_PROVIDER
    provider_name, model = _resolve_model(default)
    if get_breaker(provider_name).is_available():
        return _providers[provider_name], model

    # 6. Failover sweep
    for name in FAILOVER_ORDER:
        if get_breaker(name).is_available():
            model = _default_model_for(name)
            return _providers[name], model

    raise AllProvidersFailedError()


def _resolve_model(model_or_provider: str) -> tuple[str, str]:
    """Map a model name or provider name to (provider_name, model_id)."""
    mapping = {
        "gpt-4o":                ("openai",    "gpt-4o"),
        "gpt-4o-mini":           ("openai",    "gpt-4o-mini"),
        "gpt-4-turbo":           ("openai",    "gpt-4-turbo"),
        "claude-opus-4-6":       ("anthropic", "claude-opus-4-6"),
        "claude-sonnet-4-6":     ("anthropic", "claude-sonnet-4-6"),
        "claude-haiku-4-5-20251001":    ("anthropic", "claude-haiku-4-5-20251001"),
        "llama3-70b-8192":       ("groq",      "llama3-70b-8192"),
        "gemini-1.5-pro":        ("gemini",    "gemini-1.5-pro"),
        "gemini-1.5-flash":      ("gemini",    "gemini-1.5-flash"),
        # Provider aliases
        "openai":    ("openai",    "gpt-4o"),
        "anthropic": ("anthropic", "claude-sonnet-4-6"),
        "groq":      ("groq",      "llama3-70b-8192"),
        "gemini":    ("gemini",    "gemini-1.5-pro"),
    }
    return mapping.get(model_or_provider, ("openai", model_or_provider))


def _default_model_for(provider: str) -> str:
    return {
        "openai":    "gpt-4o",
        "anthropic": "claude-sonnet-4-6",
        "groq":      "llama3-70b-8192",
        "gemini":    "gemini-1.5-pro",
    }.get(provider, "gpt-4o")