from typing import Any, Dict, Optional
import time

from django.conf import settings
import requests


class RetryableHTTPError(requests.exceptions.HTTPError):
    pass


def is_http_error_404(error: Exception) -> bool:
    if not isinstance(error, requests.exceptions.HTTPError):
        return False

    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)

    return status_code == 404


def is_retryable_exception(exception: Exception) -> bool:
    return isinstance(exception, (requests.exceptions.Timeout, requests.exceptions.ConnectionError, RetryableHTTPError))


def is_retryable_response(response: requests.Response) -> bool:
    return response.status_code in {429, 500, 502, 503, 504}


def send_api_request(
    url: str,
    method: str = "get",
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[dict] = None,
) -> Dict[str, Any]:
    method = method.lower()
    req = getattr(requests, method)
    retries = settings.WS_EXTERNAL_API_MAX_RETRIES
    base_wait_seconds = settings.WS_EXTERNAL_API_BASE_WAIT_SECONDS
    timeout = settings.WS_EXTERNAL_API_TIMEOUT_SECONDS

    for attempt in range(retries):
        try:
            response = req(url, params=params, json=data, timeout=timeout, headers=headers)

            if is_retryable_response(response):
                raise RetryableHTTPError(f"Retryable HTTP error: {response.status_code}", response=response)

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            if is_retryable_exception(e) and attempt < retries - 1:
                wait_time = base_wait_seconds**attempt
                time.sleep(wait_time)

            else:
                raise
