from typing import List, Optional

import litellm
from django.conf import settings

from ask.constants import AIProvider
from ask.exceptions import AIKeyNotConfiguredError


DEFAULT_MODELS = {
    AIProvider.OPENAI.value: "gpt-4o-mini",
    AIProvider.ANTHROPIC.value: "claude-haiku-4-5-20251015",
    AIProvider.GOOGLE.value: "gemini/gemini-2.5-flash",
    AIProvider.CUSTOM.value: "gpt-4o-mini",
}


def get_ai_config_for_user(user, provider: Optional[str] = None, config_id: Optional[str] = None):
    """
    Get the appropriate AI provider config for a user.

    Resolution order:
    1. Specific config by config_id (if provided)
    2. User's config for the requested provider
    3. Org's config for the requested provider
    4. User's default config
    5. Org's default config

    Raises AIKeyNotConfiguredError if no valid config is found.
    """
    from users.models import AIProviderConfig

    config = AIProviderConfig.objects.get_config_for_request(
        user=user,
        provider=provider,
        config_id=config_id,
    )

    if not config:
        raise AIKeyNotConfiguredError()

    return config


def create_chat_completion(
    messages: List[dict],
    user=None,
    config_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
) -> dict:
    """
    Create a chat completion using the appropriate AI provider.

    If user is provided, will look up their AI provider configuration.
    If api_key is provided directly, uses that instead of config lookup.
    """
    resolved_api_key = api_key
    resolved_api_base = api_base
    resolved_model = model
    resolved_provider = provider

    if user and not api_key:
        config = get_ai_config_for_user(user, provider=provider, config_id=config_id)
        resolved_api_key = config.api_key
        resolved_provider = config.provider

        if config.api_base_url:
            resolved_api_base = config.api_base_url

        if not model:
            if config.model_name:
                resolved_model = config.model_name
            else:
                resolved_model = DEFAULT_MODELS.get(config.provider, "gpt-4o-mini")
    elif not api_key:
        raise AIKeyNotConfiguredError("No API key provided and no user context available.")

    if not resolved_model:
        resolved_model = settings.OPENAI_DEFAULT_CHAT_MODEL

    max_tokens = max_tokens if max_tokens is not None else settings.OPENAI_DEFAULT_CHAT_MAX_TOKENS
    temperature = temperature if temperature is not None else settings.OPENAI_DEFAULT_CHAT_TEMPERATURE

    is_gpt5_family = resolved_model.startswith("gpt-5")

    if resolved_provider == AIProvider.CUSTOM.value and resolved_api_base:
        resolved_model = f"openai/{resolved_model}"

    kwargs = dict(
        model=resolved_model,
        messages=messages,
        max_tokens=max_tokens,
        api_key=resolved_api_key,
    )

    if resolved_api_base:
        kwargs["api_base"] = resolved_api_base

    if not is_gpt5_family:
        kwargs["temperature"] = temperature

    response = litellm.completion(**kwargs)
    return response.to_dict()
