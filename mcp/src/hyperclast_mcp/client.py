"""HTTP client for the Hyperclast REST API."""

from __future__ import annotations

import re
from typing import Any, Literal

import httpx

from . import __version__

# IDs are UUIDs or short alphanumeric slugs — never path separators or query strings.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

VALID_UPDATE_MODES = ("append", "prepend", "overwrite")
UpdateMode = Literal["append", "prepend", "overwrite"]


class HyperclastAPIError(Exception):
    """An error returned by the Hyperclast API."""

    def __init__(self, status_code: int, error: str, message: str) -> None:
        self.status_code = status_code
        self.error = error
        self.message = message
        super().__init__(f"{status_code} {error}: {message}")


_STATUS_MESSAGES = {
    401: "Authentication failed — check your HYPERCLAST_TOKEN.",
    403: "Permission denied.",
    404: "Not found.",
    429: "Rate limited — try again later.",
}

_MAX_ERROR_MESSAGE_LENGTH = 500


def _validate_id(value: str, name: str) -> str:
    """Validate that a path segment ID contains only safe characters."""
    if not _SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid {name}: must contain only alphanumeric characters, hyphens, or underscores.")
    return value


class HyperclastClient:
    """Async wrapper around the Hyperclast REST API."""

    def __init__(self, base_url: str, token: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=f"{base_url}/api/v1",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Hyperclast-Client": f"client=mcp; version={__version__}",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    # -- internal helpers --------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        resp = await self._http.request(method, path, params=params, json=json)
        if resp.status_code >= 400:
            self._raise_api_error(resp)
        return resp

    @staticmethod
    def _raise_api_error(resp: httpx.Response) -> None:
        try:
            body = resp.json()
            error = body.get("error", "error")
            message = body.get("message", resp.text)
        except Exception:
            error = "error"
            message = resp.text or _STATUS_MESSAGES.get(resp.status_code, "Unknown error")

        if not message or message == error:
            message = _STATUS_MESSAGES.get(resp.status_code, f"HTTP {resp.status_code}")

        # Truncate to avoid forwarding huge error bodies into the LLM context.
        if len(message) > _MAX_ERROR_MESSAGE_LENGTH:
            message = message[:_MAX_ERROR_MESSAGE_LENGTH] + "…"

        raise HyperclastAPIError(resp.status_code, error, message)

    # -- orgs --------------------------------------------------------------

    async def list_orgs(self) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/orgs/")
        return resp.json()

    # -- projects ----------------------------------------------------------

    async def list_projects(
        self,
        org_id: str | None = None,
        include_pages: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if org_id:
            _validate_id(org_id, "org_id")
            params["org_id"] = org_id
        if include_pages:
            params["details"] = "full"
        resp = await self._request("GET", "/projects/", params=params)
        return resp.json()

    async def get_project(self, project_id: str) -> dict[str, Any]:
        _validate_id(project_id, "project_id")
        resp = await self._request("GET", f"/projects/{project_id}/", params={"details": "full"})
        return resp.json()

    # -- pages -------------------------------------------------------------

    async def list_pages(self, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        resp = await self._request("GET", "/pages/", params={"limit": limit, "offset": offset})
        return resp.json()

    async def search_pages(self, query: str) -> dict[str, Any]:
        resp = await self._request("GET", "/pages/autocomplete/", params={"q": query})
        return resp.json()

    async def get_page(self, page_id: str) -> dict[str, Any]:
        _validate_id(page_id, "page_id")
        resp = await self._request("GET", f"/pages/{page_id}/")
        return resp.json()

    async def create_page(
        self,
        project_id: str,
        title: str,
        content: str | None = None,
    ) -> dict[str, Any]:
        _validate_id(project_id, "project_id")
        body: dict[str, Any] = {"project_id": project_id, "title": title}
        if content is not None:
            body["details"] = {
                "content": content,
                "filetype": "md",
                "schema_version": 1,
            }
        resp = await self._request("POST", "/pages/", json=body)
        return resp.json()

    async def update_page(
        self,
        page_id: str,
        title: str | None = None,
        content: str | None = None,
        mode: UpdateMode = "append",
    ) -> dict[str, Any]:
        _validate_id(page_id, "page_id")
        if mode not in VALID_UPDATE_MODES:
            raise ValueError(f"Invalid mode: {mode!r}. Must be one of: {', '.join(VALID_UPDATE_MODES)}")

        # Fetch current page to preserve title if not provided
        if title is None:
            current = await self.get_page(page_id)
            title = current["title"]

        body: dict[str, Any] = {"title": title, "mode": mode}
        if content is not None:
            body["details"] = {
                "content": content,
                "filetype": "md",
                "schema_version": 1,
            }
        resp = await self._request("PUT", f"/pages/{page_id}/", json=body)
        return resp.json()

    async def delete_page(self, page_id: str) -> None:
        _validate_id(page_id, "page_id")
        await self._request("DELETE", f"/pages/{page_id}/")
