"""
Handcrafted catalog of AI models for each provider.
This provides user-friendly names and curated model lists.

Last updated: January 2026
"""

PROVIDER_MODELS = {
    "openai": [
        {
            "id": "gpt-5.2",
            "name": "GPT-5.2",
            "tier": "flagship",
            "context_window": 256000,
        },
        {
            "id": "gpt-5.2-thinking",
            "name": "GPT-5.2 Thinking",
            "tier": "reasoning",
            "context_window": 256000,
        },
        {
            "id": "gpt-5.2-codex",
            "name": "GPT-5.2 Codex",
            "tier": "coding",
            "context_window": 256000,
        },
        {
            "id": "gpt-5",
            "name": "GPT-5",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "gpt-4o",
            "name": "GPT-4o",
            "tier": "fast",
            "context_window": 128000,
        },
        {
            "id": "gpt-4o-mini",
            "name": "GPT-4o Mini",
            "tier": "budget",
            "context_window": 128000,
        },
        {
            "id": "o3",
            "name": "o3",
            "tier": "reasoning",
            "context_window": 200000,
        },
        {
            "id": "o3-mini",
            "name": "o3 Mini",
            "tier": "reasoning",
            "context_window": 200000,
        },
    ],
    "anthropic": [
        {
            "id": "claude-opus-4-5-20251124",
            "name": "Claude Opus 4.5",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "claude-sonnet-4-5-20250929",
            "name": "Claude Sonnet 4.5",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "claude-haiku-4-5-20251015",
            "name": "Claude Haiku 4.5",
            "tier": "fast",
            "context_window": 200000,
        },
        {
            "id": "claude-sonnet-4-20250514",
            "name": "Claude Sonnet 4",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "claude-opus-4-20250514",
            "name": "Claude Opus 4",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "claude-3-5-sonnet-20241022",
            "name": "Claude 3.5 Sonnet",
            "tier": "budget",
            "context_window": 200000,
        },
        {
            "id": "claude-3-5-haiku-20241022",
            "name": "Claude 3.5 Haiku",
            "tier": "budget",
            "context_window": 200000,
        },
    ],
    "google": [
        {
            "id": "gemini/gemini-3-pro",
            "name": "Gemini 3 Pro",
            "tier": "flagship",
            "context_window": 2000000,
        },
        {
            "id": "gemini/gemini-3-deep-think",
            "name": "Gemini 3 Deep Think",
            "tier": "reasoning",
            "context_window": 2000000,
        },
        {
            "id": "gemini/gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "tier": "flagship",
            "context_window": 2000000,
        },
        {
            "id": "gemini/gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "tier": "fast",
            "context_window": 1000000,
        },
        {
            "id": "gemini/gemini-2.0-flash",
            "name": "Gemini 2.0 Flash",
            "tier": "budget",
            "context_window": 1000000,
        },
    ],
    "custom": [
        {
            "id": "_custom",
            "name": "Use configured model",
            "tier": "custom",
            "context_window": None,
        },
    ],
}

DEFAULT_MODELS = {
    "openai": "gpt-5.2",
    "anthropic": "claude-sonnet-4-5-20250929",
    "google": "gemini/gemini-3-pro",
    "custom": "_custom",
}


def get_models_for_provider(provider: str) -> list:
    """Get the list of available models for a provider."""
    return PROVIDER_MODELS.get(provider, [])


def get_default_model(provider: str) -> str:
    """Get the default model ID for a provider."""
    return DEFAULT_MODELS.get(provider, "gpt-5.2")


def is_valid_model(provider: str, model_id: str) -> bool:
    """Check if a model ID is valid for the given provider."""
    if provider == "custom":
        return True
    models = PROVIDER_MODELS.get(provider, [])
    return any(m["id"] == model_id for m in models)
