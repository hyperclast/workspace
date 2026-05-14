import contextvars
from contextlib import contextmanager
from decimal import Decimal
from typing import List, Optional, Tuple, Union

import tiktoken
from django.conf import settings
from litellm import RateLimitError, Timeout, embedding

from ask.models.embedding_usage import EmbeddingUsageKind
from backend.utils import log_error
from core.helpers import retry_with_exponential_backoff


# When set (by `collect_embedding_usage()`), `_record_embedding_usage` appends
# unsaved EmbeddingUsage instances to the buffer instead of inserting one row
# per call. Lets bulk-indexing flows amortize many INSERTs into one bulk_create.
_usage_buffer_var: contextvars.ContextVar = contextvars.ContextVar("embedding_usage_buffer", default=None)


@contextmanager
def collect_embedding_usage():
    """Defer per-call EmbeddingUsage writes; yield a list of unsaved instances.

    The caller is responsible for flushing the buffer (typically via
    `EmbeddingUsage.objects.bulk_create(buffer)`). On exit the contextvar is
    reset so subsequent calls outside the block resume per-call writes.
    """
    buffer: list = []
    token = _usage_buffer_var.set(buffer)
    try:
        yield buffer
    finally:
        _usage_buffer_var.reset(token)


RETRY_ERROR_TYPES = (
    RateLimitError,
    Timeout,
)


KEY_SOURCE_EXPLICIT = "explicit"
KEY_SOURCE_SERVER = "server"
KEY_SOURCE_USER = "user"


# Per-million-token USD prices used as a fallback when litellm.completion_cost
# returns nothing for an embedding model. Treat as a "last resort" lookup —
# the source of truth is the provider's published pricing, and litellm's cost
# map should generally agree.
EMBEDDING_COST_PER_MILLION_TOKENS = {
    "text-embedding-3-small": Decimal("0.02"),
    "text-embedding-3-large": Decimal("0.13"),
    "text-embedding-ada-002": Decimal("0.10"),
}


def _resolve_credentials(
    user=None, api_key: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], str, Optional[object]]:
    """Resolve (api_key, api_base_url, key_source, org) for an embedding call.

    `org` is the `Org` whose shared `AIProviderConfig` is paying — None for
    explicit / server / personal-config paths. It identifies the paying entity
    for audit attribution, not the requesting user's membership.

    Precedence:
        1. Explicit `api_key` argument (tests, scripts).
        2. Server-side `EMBEDDINGS_SERVER_API_KEY` setting (hosted product).
        3. The user/org's OpenAI AIProviderConfig (self-host fallback).
    """
    if api_key:
        return api_key, None, KEY_SOURCE_EXPLICIT, None

    server_key = getattr(settings, "EMBEDDINGS_SERVER_API_KEY", "") or ""
    if server_key:
        base_url = getattr(settings, "EMBEDDINGS_SERVER_API_BASE_URL", "") or ""
        return server_key, (base_url or None), KEY_SOURCE_SERVER, None

    if user is not None:
        from ask.constants import AIProvider
        from users.models import AIProviderConfig

        config_obj = AIProviderConfig.objects.get_config_for_request(user, provider=AIProvider.OPENAI.value)
        if config_obj and config_obj.api_key and config_obj.provider == AIProvider.OPENAI.value:
            return (
                config_obj.api_key,
                (config_obj.api_base_url or None),
                KEY_SOURCE_USER,
                config_obj.org,
            )

    return None, None, "", None


def has_embedding_credentials(user=None) -> bool:
    """Return True when any credential source can satisfy an embedding call."""
    api_key, _, _, _ = _resolve_credentials(user=user)
    return bool(api_key)


def _extract_usage_tokens(response) -> Tuple[Optional[int], Optional[int]]:
    """Pull prompt/total tokens from a litellm response, tolerating dict + object shapes."""
    usage = getattr(response, "usage", None)
    if usage is None and isinstance(response, dict):
        usage = response.get("usage")

    if isinstance(usage, dict):
        prompt = usage.get("prompt_tokens")
        total = usage.get("total_tokens")
    elif usage is not None:
        prompt = getattr(usage, "prompt_tokens", None)
        total = getattr(usage, "total_tokens", None)
    else:
        return None, None

    if not isinstance(prompt, int) or not isinstance(total, int):
        return None, None
    return prompt, total


def _compute_embedding_cost(*, response, model: str, total_tokens: int) -> Decimal:
    """Compute USD cost for an embedding call.

    Asks litellm first (it knows the published rate cards); falls back to
    a per-model rate table if litellm has no answer.
    """
    try:
        from litellm import completion_cost

        cost = completion_cost(completion_response=response)
        if cost:
            return Decimal(str(cost))
    except Exception:
        pass

    rate_per_million = EMBEDDING_COST_PER_MILLION_TOKENS.get(model)
    if rate_per_million is None or total_tokens <= 0:
        return Decimal("0")
    return (Decimal(total_tokens) / Decimal(1_000_000) * rate_per_million).quantize(Decimal("0.00000001"))


def _record_embedding_usage(*, response, model: str, user, org, page, kind: EmbeddingUsageKind, key_source: str):
    """Persist one EmbeddingUsage row per successful embedding call.

    Best-effort: any failure here is logged but never blocks the caller.
    A response whose shape we don't understand (e.g. a bare Mock) is skipped
    silently so unit tests that mock `litellm.embedding` stay green.

    When called inside `collect_embedding_usage()`, the row is appended (unsaved)
    to the active buffer instead of being INSERTed, so the caller can flush
    many rows via a single `bulk_create`.
    """
    try:
        from ask.models import EmbeddingUsage, EmbeddingUsageKeySource

        prompt_tokens, total_tokens = _extract_usage_tokens(response)
        if prompt_tokens is None or total_tokens is None:
            return

        if kind not in EmbeddingUsageKind.values or key_source not in EmbeddingUsageKeySource.values:
            return

        cost = _compute_embedding_cost(response=response, model=model, total_tokens=total_tokens)

        usage = EmbeddingUsage(
            user=user,
            org=org,
            page=page,
            model=model,
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            kind=kind,
            key_source=key_source,
        )

        buffer = _usage_buffer_var.get()
        if buffer is not None:
            buffer.append(usage)
            return

        usage.save()
    except Exception as exc:
        log_error("EmbeddingUsage record failed (%s): %s", type(exc).__name__, exc)


@retry_with_exponential_backoff(errors=RETRY_ERROR_TYPES)
def create_embedding(input_data: str, **options) -> List[float]:
    """Creates embedding for the given `input_data` and records usage.

    `options["kind"]` accepts an `EmbeddingUsageKind` member or its underlying
    string value (TextChoices is a str-enum, so the two are equal). A typo'd
    string raises ValueError up front rather than silently dropping the
    audit row deep inside `_record_embedding_usage`.
    """
    model = options.get("model", settings.ASK_EMBEDDINGS_DEFAULT_MODEL)
    user = options.get("user")
    page = options.get("page")
    kind: EmbeddingUsageKind = options.get("kind", EmbeddingUsageKind.QUERY)

    if kind not in EmbeddingUsageKind.values:
        raise ValueError(f"Invalid kind {kind!r}; expected one of {sorted(EmbeddingUsageKind.values)}")

    api_key, api_base_url, key_source, org = _resolve_credentials(user=user, api_key=options.get("api_key"))

    if not api_key:
        raise ValueError("api_key is required for creating embeddings - configure an AI provider in settings")

    call_kwargs = {"input": [input_data], "model": model, "api_key": api_key}
    if api_base_url:
        call_kwargs["api_base"] = api_base_url

    response = embedding(**call_kwargs)

    _record_embedding_usage(
        response=response,
        model=model,
        user=user,
        org=org,
        page=page,
        kind=kind,
        key_source=key_source,
    )

    return response.data[0]["embedding"]


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
    user=None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    encoding_name: Optional[str] = None,
    max_tokens: Optional[int] = None,
    raise_exception: Optional[bool] = False,
    page=None,
    kind: EmbeddingUsageKind = EmbeddingUsageKind.QUERY,
) -> Union[List[float], None]:
    """Computes embedding for given `data`. Requires user or api_key to resolve credentials."""
    result = None

    try:
        model = model or settings.ASK_EMBEDDINGS_DEFAULT_MODEL
        encoding_name = encoding_name or settings.ASK_EMBEDDINGS_DEFAULT_ENCODING
        max_tokens = max_tokens or settings.ASK_EMBEDDINGS_DEFAULT_MAX_INPUT

        input_data = truncate_input_data(data=data, encoding_name=encoding_name, max_tokens=max_tokens)
        result = create_embedding(
            input_data=input_data,
            model=model,
            api_key=api_key,
            user=user,
            page=page,
            kind=kind,
        )

    except Exception as e:
        if raise_exception:
            raise e

        log_error(f"Embeddings: Encountered error {e}")

    return result
