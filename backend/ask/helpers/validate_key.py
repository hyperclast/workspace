from typing import Optional, Tuple

import litellm
from django.utils import timezone

from ask.constants import AIProvider
from ask.exceptions import AIKeyValidationError


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


def _validate_openai_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """Validate OpenAI API key using litellm."""
    try:
        response = litellm.completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            api_key=api_key,
        )
        return True, None
    except litellm.AuthenticationError:
        return False, "Invalid API key"
    except litellm.RateLimitError:
        return True, None
    except litellm.APIError as e:
        if "invalid_api_key" in str(e).lower() or "incorrect api key" in str(e).lower():
            return False, "Invalid API key"
        return True, None
    except Exception as e:
        error_str = str(e).lower()
        if "invalid" in error_str and "key" in error_str:
            return False, "Invalid API key"
        if "authentication" in error_str or "unauthorized" in error_str:
            return False, "Invalid API key"
        return False, f"Validation failed: {str(e)}"


def _validate_anthropic_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """Validate Anthropic API key using litellm."""
    try:
        response = litellm.completion(
            model="claude-3-5-haiku-20241022",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            api_key=api_key,
        )
        return True, None
    except litellm.AuthenticationError:
        return False, "Invalid API key"
    except litellm.RateLimitError:
        return True, None
    except litellm.APIError as e:
        if "invalid" in str(e).lower() and "key" in str(e).lower():
            return False, "Invalid API key"
        return True, None
    except Exception as e:
        error_str = str(e).lower()
        if "invalid" in error_str and "key" in error_str:
            return False, "Invalid API key"
        if "authentication" in error_str or "unauthorized" in error_str:
            return False, "Invalid API key"
        return False, f"Validation failed: {str(e)}"


def _validate_google_key(api_key: str) -> Tuple[bool, Optional[str]]:
    """Validate Google Gemini API key using litellm."""
    try:
        response = litellm.completion(
            model="gemini/gemini-2.0-flash",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
            api_key=api_key,
        )
        return True, None
    except litellm.AuthenticationError:
        return False, "Invalid API key"
    except litellm.RateLimitError:
        return True, None
    except litellm.APIError as e:
        if "invalid" in str(e).lower() and "key" in str(e).lower():
            return False, "Invalid API key"
        return True, None
    except Exception as e:
        error_str = str(e).lower()
        if "invalid" in error_str and "key" in error_str:
            return False, "Invalid API key"
        if "authentication" in error_str or "unauthorized" in error_str:
            return False, "Invalid API key"
        return False, f"Validation failed: {str(e)}"


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
    config.save(update_fields=["is_validated", "last_validated_at", "modified"])

    return is_valid, error
