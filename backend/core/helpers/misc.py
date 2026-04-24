from functools import reduce
from typing import Any, Iterable, List, Optional
import operator
import uuid


def chunked(iterable: List[Any], batch_size: int) -> Iterable[List[Any]]:
    for i in range(0, len(iterable), batch_size):
        yield iterable[i : i + batch_size]


def get_from_nested_dict(data: dict, dotted_keys: str, default: Optional[Any] = None) -> Any:
    """Gets value from nested dict using keys as dotted path."""
    keys = [k.strip() for k in dotted_keys.split(".")]
    try:
        return reduce(operator.getitem, keys, data)
    except (KeyError, TypeError):
        return default


def is_valid_uuid(value: Any) -> bool:
    """True if `value` parses as a UUID.

    Used to guard `filter(uuid_field__in=[...])` calls against malformed
    external IDs that would otherwise raise DataError on Postgres.

    `uuid.UUID` raises TypeError on `None` / non-string input (Python 3.13),
    ValueError on strings that aren't valid UUIDs, and AttributeError on
    some older paths; all three collapse to "not a UUID" for this helper.
    """
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
