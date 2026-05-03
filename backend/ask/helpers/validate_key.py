from typing import Optional, Tuple

import litellm
import requests
from django.utils import timezone

from ask.constants import AIProvider
from core.helpers.api import send_api_request


OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
GOOGLE_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def validate_api_key(
    provider: str,
    api_key: str,
    api_base_url: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate an AI provider API key by making a minimal test request.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key and provider != AIProvider.CUSTOM.value:
        return False, "API key is required"

    try:
        if provider == AIProvider.OPENAI.value:
            return _validate_openai_key(api_key)
        elif provider == AIProvider.ANTHROPIC.value:
            return _validate_anthropic_key(api_key)
        elif provider == AIProvider.GOOGLE.value:
            return _validate_google_key(api_key)
        elif provider == AIProvider.CUSTOM.value:
            return _validate_custom_key(api_key, api_base_url, model_name)
        else:
            return False, f"Unknown provider: {provider}"
    except Exception as e:
        return False, str(e)


def _invalid_key_status_codes(provider: str) -> set:
    # Google returns 400 for an invalid key; OpenAI/Anthropic use 401.
    # 403 = key valid but disabled/restricted; treat as invalid for our purposes.
    if provider == AIProvider.GOOGLE.value:
        return {400, 401, 403}
    return {401, 403}


def _validate_via_models(provider: str, url: str, headers: dict) -> Tuple[bool, Optional[str]]:
    try:
        send_api_request(url, method="get", headers=headers)
        return True, None
    except requests.exceptions.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status in _invalid_key_status_codes(provider):
            return False, "Invalid API key"
        return False, f"Validation failed: HTTP {status}"
    except requests.exceptions.RequestException as e:
        return False, f"Validation failed: {e}"


def _validate_openai_key(api_key: str) -> Tuple[bool, Optional[str]]:
    return _validate_via_models(
        AIProvider.OPENAI.value,
        OPENAI_MODELS_URL,
        {"Authorization": f"Bearer {api_key}"},
    )


def _validate_anthropic_key(api_key: str) -> Tuple[bool, Optional[str]]:
    return _validate_via_models(
        AIProvider.ANTHROPIC.value,
        ANTHROPIC_MODELS_URL,
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )


def _validate_google_key(api_key: str) -> Tuple[bool, Optional[str]]:
    return _validate_via_models(
        AIProvider.GOOGLE.value,
        GOOGLE_MODELS_URL,
        {"x-goog-api-key": api_key},
    )


def _validate_custom_key(
    api_key: str,
    api_base_url: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Validate custom OpenAI-compatible API endpoint."""
    if not api_base_url:
        return False, "API base URL is required for custom providers"

    model = model_name or "gpt-3.5-turbo"

    try:
        kwargs = {
            "model": f"openai/{model}",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 1,
            "api_base": api_base_url,
        }
        if api_key:
            kwargs["api_key"] = api_key

        response = litellm.completion(**kwargs)
        return True, None
    except litellm.AuthenticationError:
        return False, "Invalid API key"
    except litellm.RateLimitError:
        return True, None
    except litellm.APIConnectionError:
        return False, f"Could not connect to {api_base_url}"
    except Exception as e:
        error_str = str(e).lower()
        if "invalid" in error_str and "key" in error_str:
            return False, "Invalid API key"
        if "authentication" in error_str or "unauthorized" in error_str:
            return False, "Invalid API key"
        if "connection" in error_str or "connect" in error_str:
            return False, f"Could not connect to {api_base_url}"
        return False, f"Validation failed: {str(e)}"


def validate_and_update_config(config) -> Tuple[bool, Optional[str]]:
    """
    Validate an AIProviderConfig and update its validation status.

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_api_key(
        provider=config.provider,
        api_key=config.api_key,
        api_base_url=config.api_base_url,
        model_name=config.model_name,
    )

    config.is_validated = is_valid
    if is_valid:
        config.last_validated_at = timezone.now()
        config.is_enabled = True
    config.save(update_fields=["is_validated", "last_validated_at", "is_enabled", "modified"])

    return is_valid, error
