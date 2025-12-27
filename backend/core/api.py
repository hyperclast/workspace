import re
from urllib.parse import urlparse

import requests
from django.http import HttpRequest
from ninja import Router, Schema

from core.throttling import UrlTitleThrottle

router = Router(tags=["utils"])


class UrlTitleRequest(Schema):
    url: str


class UrlTitleResponse(Schema):
    title: str | None
    error: str | None = None


@router.post("/url-title/", response=UrlTitleResponse, auth=None, throttle=[UrlTitleThrottle()])
def fetch_url_title(request: HttpRequest, data: UrlTitleRequest):
    url = data.url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return {"title": None, "error": "Invalid URL"}
    except Exception:
        return {"title": None, "error": "Invalid URL"}

    try:
        response = requests.get(
            url,
            timeout=3,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Hyperclast/1.0)",
                "Accept": "text/html",
            },
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return {"title": parsed.netloc, "error": None}

        html = response.text[:50000]

        og_match = re.search(
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not og_match:
            og_match = re.search(
                r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']',
                html,
                re.IGNORECASE,
            )

        if og_match:
            return {"title": og_match.group(1).strip(), "error": None}

        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            title = re.sub(r"\s+", " ", title)
            return {"title": title, "error": None}

        return {"title": parsed.netloc, "error": None}

    except requests.Timeout:
        return {"title": parsed.netloc, "error": None}
    except Exception:
        return {"title": parsed.netloc, "error": None}
