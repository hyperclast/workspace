from typing import List, Optional

import litellm
from django.conf import settings


def create_chat_completion(
    messages: List[dict],
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    api_key: Optional[str] = None,
) -> dict:
    model = model or settings.OPENAI_DEFAULT_CHAT_MODEL
    max_tokens = max_tokens if max_tokens is not None else settings.OPENAI_DEFAULT_CHAT_MAX_TOKENS
    temperature = temperature if temperature is not None else settings.OPENAI_DEFAULT_CHAT_TEMPERATURE
    api_key = api_key or settings.OPENAI_API_KEY

    is_gpt5_family = model.startswith("gpt-5")

    kwargs = dict(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        api_key=api_key,
    )

    # GPT-5 family models do not allow changing temperature away from the default
    # So only allow setting temperature for other models
    # Ref: https://community.openai.com/t/gpt-5-models-temperature/1337957?utm_source=chatgpt.com

    if not is_gpt5_family:
        kwargs["temperature"] = temperature

    response = litellm.completion(**kwargs)
    return response.to_dict()
