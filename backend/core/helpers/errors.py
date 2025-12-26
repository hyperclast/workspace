from typing import Callable, Optional
import functools
import random
import time

from core.exceptions import MaxRetriesExceeded


def retry_with_exponential_backoff(
    f: Optional[Callable] = None,
    *,
    base_delay: Optional[float] = 1,
    exponential_base: Optional[float] = 2,
    jitter: Optional[bool] = True,
    max_retries: Optional[int] = 10,
    errors: Optional[tuple] = (Exception,),
    initial_pause: Optional[float] = None,
):
    """Retries a function with exponential backoff."""

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            num_retries = 0
            delay = base_delay

            if initial_pause is not None:
                time.sleep(initial_pause)

            # Loop until a successful response or max_retries is hit or an exception is raised
            while True:
                try:
                    return func(*args, **kwargs)

                except errors as e:
                    num_retries += 1

                    if num_retries > max_retries:
                        raise MaxRetriesExceeded(f"Maximum number of retries ({max_retries}) exceeded.")

                    delay *= exponential_base * (1 + jitter * random.random())
                    time.sleep(delay)

                except Exception as e:
                    raise e

        return wrapper

    if callable(f):
        return decorator(f)

    return decorator
