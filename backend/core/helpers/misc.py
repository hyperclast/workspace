from functools import reduce
from typing import Any, Iterable, List, Optional
import operator


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
