"""Tests for the Hyperclast API client."""

import json

import httpx
import pytest

from hyperclast_mcp import __version__
from hyperclast_mcp.client import HyperclastAPIError, HyperclastClient, _validate_id


def _mock_transport(handler):
    """Create an httpx MockTransport from a handler function.

    handler(request) -> httpx.Response
    """
    return httpx.MockTransport(handler)


def _json_response(data, status_code=200):
    return httpx.Response(status_code, json=data)


def _error_response(status_code, error="error", message="Something went wrong"):
    return httpx.Response(status_code, json={"error": error, "message": message})


def _make_client(handler) -> HyperclastClient:
    """Create a HyperclastClient with a mocked transport."""
    client = HyperclastClient("https://test.example.com", "test-token")
    # Replace the internal httpx client with one using our mock transport
    client._http = httpx.AsyncClient(
        transport=_mock_transport(handler),
        base_url="https://test.example.com/api/v1",
        headers=client._http.headers,
        timeout=30.0,
    )
    return client


def _noop_handler(request):
    return _json_response({})


# -- ID validation ----------------------------------------------------------


class TestValidateId:
    def test_accepts_alphanumeric(self):
        assert _validate_id("abc123", "id") == "abc123"

    def test_accepts_hyphens(self):
        assert _validate_id("my-project-id", "id") == "my-project-id"

    def test_accepts_underscores(self):
        assert _validate_id("my_page_id", "id") == "my_page_id"

    def test_accepts_uuid_style(self):
        assert _validate_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890", "id")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("../../admin", "id")

    def test_rejects_slashes(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("foo/bar", "id")

    def test_rejects_query_string(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("id?extra=1", "id")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("", "id")

    def test_rejects_spaces(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("foo bar", "id")

    def test_rejects_url_encoded_slash(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("foo%2fbar", "id")

    def test_error_message_includes_field_name(self):
        with pytest.raises(ValueError, match="project_id"):
            _validate_id("../evil", "project_id")


class TestIdValidationInMethods:
    """Verify that all methods with path-interpolated IDs validate them."""

    @pytest.mark.asyncio
    async def test_get_project_rejects_bad_id(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="project_id"):
            await client.get_project("../../admin")

    @pytest.mark.asyncio
    async def test_get_page_rejects_bad_id(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="page_id"):
            await client.get_page("foo/bar")

    @pytest.mark.asyncio
    async def test_create_page_rejects_bad_project_id(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="project_id"):
            await client.create_page("bad id!", "Title")

    @pytest.mark.asyncio
    async def test_update_page_rejects_bad_id(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="page_id"):
            await client.update_page("../etc/passwd", title="Title")

    @pytest.mark.asyncio
    async def test_delete_page_rejects_bad_id(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="page_id"):
            await client.delete_page("id?admin=true")

    @pytest.mark.asyncio
    async def test_list_projects_rejects_bad_org_id(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="org_id"):
            await client.list_projects(org_id="../../admin")


# -- Mode validation --------------------------------------------------------


class TestModeValidation:
    @pytest.mark.asyncio
    async def test_rejects_invalid_mode(self):
        client = _make_client(_noop_handler)
        with pytest.raises(ValueError, match="Invalid mode"):
            await client.update_page("p1", title="T", mode="drop_table")

    @pytest.mark.asyncio
    async def test_accepts_append(self):
        def handler(request):
            return _json_response({"external_id": "p1", "title": "T"})

        client = _make_client(handler)
        await client.update_page("p1", title="T", mode="append")

    @pytest.mark.asyncio
    async def test_accepts_prepend(self):
        def handler(request):
            return _json_response({"external_id": "p1", "title": "T"})

        client = _make_client(handler)
        await client.update_page("p1", title="T", mode="prepend")

    @pytest.mark.asyncio
    async def test_accepts_overwrite(self):
        def handler(request):
            return _json_response({"external_id": "p1", "title": "T"})

        client = _make_client(handler)
        await client.update_page("p1", title="T", mode="overwrite")


# -- Headers ----------------------------------------------------------------


class TestClientHeaders:
    @pytest.mark.asyncio
    async def test_sends_auth_header(self):
        captured = {}

        def handler(request):
            captured["auth"] = request.headers.get("authorization")
            return _json_response([])

        client = _make_client(handler)
        await client.list_orgs()
        assert captured["auth"] == "Bearer test-token"

    @pytest.mark.asyncio
    async def test_sends_client_header(self):
        captured = {}

        def handler(request):
            captured["client"] = request.headers.get("x-hyperclast-client")
            return _json_response([])

        client = _make_client(handler)
        await client.list_orgs()
        assert captured["client"] == f"client=mcp; version={__version__}"


# -- Error handling ---------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_api_error_with_json_body(self):
        def handler(request):
            return _error_response(403, "forbidden", "Permission denied.")

        client = _make_client(handler)
        with pytest.raises(HyperclastAPIError) as exc_info:
            await client.list_orgs()
        assert exc_info.value.status_code == 403
        assert exc_info.value.error == "forbidden"
        assert exc_info.value.message == "Permission denied."

    @pytest.mark.asyncio
    async def test_api_error_with_non_json_body(self):
        def handler(request):
            return httpx.Response(500, text="Internal Server Error")

        client = _make_client(handler)
        with pytest.raises(HyperclastAPIError) as exc_info:
            await client.list_orgs()
        assert exc_info.value.status_code == 500
        assert exc_info.value.message == "Internal Server Error"

    @pytest.mark.asyncio
    async def test_api_error_with_empty_body(self):
        def handler(request):
            return httpx.Response(401, text="")

        client = _make_client(handler)
        with pytest.raises(HyperclastAPIError) as exc_info:
            await client.list_orgs()
        assert exc_info.value.status_code == 401
        assert "Authentication failed" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_404_uses_fallback_message(self):
        def handler(request):
            return httpx.Response(404, text="")

        client = _make_client(handler)
        with pytest.raises(HyperclastAPIError) as exc_info:
            await client.get_page("nonexistent")
        assert exc_info.value.message == "Not found."

    @pytest.mark.asyncio
    async def test_huge_error_message_is_truncated(self):
        huge_message = "x" * 2000

        def handler(request):
            return _error_response(500, "error", huge_message)

        client = _make_client(handler)
        with pytest.raises(HyperclastAPIError) as exc_info:
            await client.list_orgs()
        assert len(exc_info.value.message) == 501  # 500 chars + ellipsis
        assert exc_info.value.message.endswith("…")


# -- Close ------------------------------------------------------------------


class TestClose:
    @pytest.mark.asyncio
    async def test_close_shuts_down_http_client(self):
        client = _make_client(_noop_handler)
        await client.close()
        assert client._http.is_closed


# -- Orgs -------------------------------------------------------------------


class TestListOrgs:
    @pytest.mark.asyncio
    async def test_returns_org_list(self):
        orgs = [{"external_id": "org1", "name": "My Org"}]

        def handler(request):
            assert request.url.path == "/api/v1/orgs/"
            return _json_response(orgs)

        client = _make_client(handler)
        result = await client.list_orgs()
        assert result == orgs


# -- Projects ---------------------------------------------------------------


class TestListProjects:
    @pytest.mark.asyncio
    async def test_no_filters(self):
        projects = [{"external_id": "proj1", "name": "Project"}]

        def handler(request):
            assert request.url.path == "/api/v1/projects/"
            assert b"org_id" not in request.url.query
            assert b"details" not in request.url.query
            return _json_response(projects)

        client = _make_client(handler)
        result = await client.list_projects()
        assert result == projects

    @pytest.mark.asyncio
    async def test_with_org_id_filter(self):
        def handler(request):
            assert "org_id=org1" in str(request.url)
            return _json_response([])

        client = _make_client(handler)
        await client.list_projects(org_id="org1")

    @pytest.mark.asyncio
    async def test_with_include_pages(self):
        def handler(request):
            assert "details=full" in str(request.url)
            return _json_response([])

        client = _make_client(handler)
        await client.list_projects(include_pages=True)


class TestGetProject:
    @pytest.mark.asyncio
    async def test_fetches_with_full_details(self):
        project = {"external_id": "proj1", "name": "Project", "pages": []}

        def handler(request):
            assert "/projects/proj1/" in request.url.path
            assert "details=full" in str(request.url)
            return _json_response(project)

        client = _make_client(handler)
        result = await client.get_project("proj1")
        assert result == project


# -- Pages ------------------------------------------------------------------


class TestListPages:
    @pytest.mark.asyncio
    async def test_default_pagination(self):
        data = {"items": [], "count": 0}

        def handler(request):
            assert "limit=100" in str(request.url)
            assert "offset=0" in str(request.url)
            return _json_response(data)

        client = _make_client(handler)
        result = await client.list_pages()
        assert result == data

    @pytest.mark.asyncio
    async def test_custom_pagination(self):
        def handler(request):
            assert "limit=10" in str(request.url)
            assert "offset=20" in str(request.url)
            return _json_response({"items": [], "count": 0})

        client = _make_client(handler)
        await client.list_pages(limit=10, offset=20)


class TestSearchPages:
    @pytest.mark.asyncio
    async def test_sends_query(self):
        data = {"pages": [{"external_id": "p1", "title": "Meeting notes"}]}

        def handler(request):
            assert request.url.path == "/api/v1/pages/autocomplete/"
            assert "q=meeting" in str(request.url)
            return _json_response(data)

        client = _make_client(handler)
        result = await client.search_pages("meeting")
        assert result == data


class TestGetPage:
    @pytest.mark.asyncio
    async def test_returns_page(self):
        page = {
            "external_id": "p1",
            "title": "My Page",
            "details": {"content": "Hello", "filetype": "md"},
        }

        def handler(request):
            assert "/pages/p1/" in request.url.path
            return _json_response(page)

        client = _make_client(handler)
        result = await client.get_page("p1")
        assert result == page


class TestCreatePage:
    @pytest.mark.asyncio
    async def test_create_without_content(self):
        def handler(request):
            body = json.loads(request.content)
            assert body == {"project_id": "proj1", "title": "New Page"}
            return _json_response({"external_id": "p1", "title": "New Page"}, 201)

        client = _make_client(handler)
        result = await client.create_page("proj1", "New Page")
        assert result["title"] == "New Page"

    @pytest.mark.asyncio
    async def test_create_with_content(self):
        def handler(request):
            body = json.loads(request.content)
            assert body["details"] == {
                "content": "# Hello",
                "filetype": "md",
                "schema_version": 1,
            }
            return _json_response({"external_id": "p1", "title": "Page"}, 201)

        client = _make_client(handler)
        await client.create_page("proj1", "Page", content="# Hello")


class TestUpdatePage:
    @pytest.mark.asyncio
    async def test_update_with_explicit_title(self):
        def handler(request):
            body = json.loads(request.content)
            assert body["title"] == "New Title"
            assert body["mode"] == "append"
            return _json_response({"external_id": "p1", "title": "New Title"})

        client = _make_client(handler)
        await client.update_page("p1", title="New Title")

    @pytest.mark.asyncio
    async def test_update_preserves_title_when_omitted(self):
        """When title is None, client fetches current page to get the title."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if request.method == "GET":
                return _json_response(
                    {
                        "external_id": "p1",
                        "title": "Original Title",
                        "details": {"content": "old"},
                    }
                )
            # PUT
            body = json.loads(request.content)
            assert body["title"] == "Original Title"
            assert body["details"]["content"] == "new content"
            return _json_response({"external_id": "p1", "title": "Original Title"})

        client = _make_client(handler)
        await client.update_page("p1", content="new content")
        assert call_count == 2  # GET + PUT

    @pytest.mark.asyncio
    async def test_update_with_overwrite_mode(self):
        def handler(request):
            body = json.loads(request.content)
            assert body["mode"] == "overwrite"
            return _json_response({"external_id": "p1", "title": "Title"})

        client = _make_client(handler)
        await client.update_page("p1", title="Title", content="replaced", mode="overwrite")


class TestDeletePage:
    @pytest.mark.asyncio
    async def test_sends_delete(self):
        def handler(request):
            assert request.method == "DELETE"
            assert "/pages/p1/" in request.url.path
            return httpx.Response(204)

        client = _make_client(handler)
        await client.delete_page("p1")
