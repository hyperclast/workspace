from typing import List, Optional, Union

import tiktoken
from django.conf import settings
from litellm import embedding, RateLimitError, Timeout

from backend.utils import log_error
from core.helpers import retry_with_exponential_backoff


RETRY_ERROR_TYPES = (
    RateLimitError,
    Timeout,
)


@retry_with_exponential_backoff(errors=RETRY_ERROR_TYPES)
def create_embedding(input_data: str, **options) -> List[float]:
    """Creates embedding for the given `input_data`."""
    model = options.get("model", settings.ASK_EMBEDDINGS_DEFAULT_MODEL)
    api_key = options.get("api_key", settings.OPENAI_API_KEY)

    return embedding(input=[input_data], model=model, api_key=api_key).data[0]["embedding"]


def truncate_input_data(data: str, encoding_name: str, max_tokens: int) -> str:
    """Ensures that `data` doesn't exceed token limits."""
    encoding = tiktoken.get_encoding(encoding_name)
    encoded_tokens = encoding.encode(data)
    num_tokens = len(encoded_tokens)

    if num_tokens <= max_tokens:
        return data

    truncated_tokens = encoded_tokens[:max_tokens]
    result = encoding.decode(truncated_tokens)

    return result


def compute_embedding(
    data: str,
    model: Optional[str] = None,
    encoding_name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    api_key: Optional[str] = None,
    raise_exception: Optional[bool] = False,
) -> Union[List[float], None]:
    """Computes embedding for given `data`."""
    embedding = None

    try:
        api_key = api_key or settings.OPENAI_API_KEY
        model = model or settings.ASK_EMBEDDINGS_DEFAULT_MODEL
        encoding_name = encoding_name or settings.ASK_EMBEDDINGS_DEFAULT_ENCODING
        max_tokens = max_tokens or settings.ASK_EMBEDDINGS_DEFAULT_MAX_INPUT

        input_data = truncate_input_data(data=data, encoding_name=encoding_name, max_tokens=max_tokens)
        embedding = create_embedding(input_data=input_data, model=model, api_key=api_key)

    except Exception as e:
        if raise_exception:
            raise e

        log_error(f"Embeddings: Encountered error {e}")

    return embedding
