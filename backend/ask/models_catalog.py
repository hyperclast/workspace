"""
Handcrafted catalog of AI models for each provider.
This provides user-friendly names and curated model lists.

Last updated: April 2026
"""

PROVIDER_MODELS = {
    "openai": [
        {
            "id": "gpt-5.4",
            "name": "GPT-5.4",
            "tier": "flagship",
            "context_window": 256000,
        },
        {
            "id": "gpt-5.4-mini",
            "name": "GPT-5.4 Mini",
            "tier": "fast",
            "context_window": 256000,
        },
        {
            "id": "gpt-5.4-nano",
            "name": "GPT-5.4 Nano",
            "tier": "budget",
            "context_window": 256000,
        },
    ],
    "anthropic": [
        {
            "id": "claude-opus-4-7",
            "name": "Claude Opus 4.7",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "claude-sonnet-4-6",
            "name": "Claude Sonnet 4.6",
            "tier": "flagship",
            "context_window": 200000,
        },
        {
            "id": "claude-haiku-4-5",
            "name": "Claude Haiku 4.5",
            "tier": "fast",
            "context_window": 200000,
        },
    ],
    "google": [
        {
            "id": "gemini/gemini-3.1-pro-preview",
            "name": "Gemini 3.1 Pro (Preview)",
            "tier": "flagship",
            "context_window": 1048576,
        },
        {
            "id": "gemini/gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "tier": "flagship",
            "context_window": 1048576,
        },
        {
            "id": "gemini/gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "tier": "fast",
            "context_window": 1048576,
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
    "openai": "gpt-5.4",
    "anthropic": "claude-sonnet-4-6",
    "google": "gemini/gemini-3.1-pro-preview",
    "custom": "_custom",
}


def get_models_for_provider(provider: str) -> list:
    """Get the list of available models for a provider."""
    return PROVIDER_MODELS.get(provider, [])


def get_default_model(provider: str) -> str:
    """Get the default model ID for a provider."""
    return DEFAULT_MODELS.get(provider, "gpt-5.4")


def is_valid_model(provider: str, model_id: str) -> bool:
    """Check if a model ID is valid for the given provider."""
    if provider == "custom":
        return True
    models = PROVIDER_MODELS.get(provider, [])
    return any(m["id"] == model_id for m in models)
