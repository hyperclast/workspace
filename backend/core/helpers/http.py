from typing import Optional, Union
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import re
from django.conf import settings
from django.http import HttpRequest


def get_ip(request: HttpRequest) -> Union[str, None]:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip


def get_host(url: str) -> str:
    return urlparse(url).netloc


def clean_url(url: str) -> str:
    """Removes tracking params from URL."""
    if not url:
        return ""

    parsed = urlparse(url)
    clean_query = {k: v for k, v in parse_qs(parsed.query).items() if not k.startswith("utm_")}
    clean_url = parsed._replace(query=urlencode(clean_query, doseq=True)).geturl()

    return clean_url.strip()


def build_full_url(base_url: Optional[str] = None, path: Optional[str] = None) -> None:
    base_url = base_url or settings.WS_ROOT_URL
    path = path or ""
    url = urljoin(base_url, path)

    return url
