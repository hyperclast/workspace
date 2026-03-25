"""Tests for MCP server tool functions."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from hyperclast_mcp.client import HyperclastAPIError
from hyperclast_mcp import server as server_module


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the global client before each test."""
    server_module._client = None
    yield
    server_module._client = None


@pytest.fixture
def mock_client():
    """Provide a mock HyperclastClient and inject it into the server module."""
    client = AsyncMock()
    server_module._client = client
    return client


def _parse(result: str):
    """Parse a JSON tool result."""
    return json.loads(result)


# -- Orgs -------------------------------------------------------------------


class TestListOrgsTool:
    @pytest.mark.asyncio
    async def test_returns_orgs_as_json(self, mock_client):
        mock_client.list_orgs.return_value = [{"external_id": "org1", "name": "My Org", "is_pro": False}]
        result = await server_module.list_orgs()
        parsed = _parse(result)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "My Org"

    @pytest.mark.asyncio
    async def test_returns_error_message(self, mock_client):
        mock_client.list_orgs.side_effect = HyperclastAPIError(401, "unauthorized", "Authentication failed.")
        result = await server_module.list_orgs()
        assert result == "Error: Authentication failed."


# -- Projects ---------------------------------------------------------------


class TestListProjectsTool:
    @pytest.mark.asyncio
    async def test_passes_filters(self, mock_client):
        mock_client.list_projects.return_value = []
        await server_module.list_projects(org_id="org1", include_pages=True)
        mock_client.list_projects.assert_called_once_with("org1", True)

    @pytest.mark.asyncio
    async def test_defaults(self, mock_client):
        mock_client.list_projects.return_value = []
        await server_module.list_projects()
        mock_client.list_projects.assert_called_once_with(None, False)

    @pytest.mark.asyncio
    async def test_error(self, mock_client):
        mock_client.list_projects.side_effect = HyperclastAPIError(403, "forbidden", "Permission denied.")
        result = await server_module.list_projects()
        assert "Error: Permission denied." == result

    @pytest.mark.asyncio
    async def test_validation_error_returns_message(self, mock_client):
        mock_client.list_projects.side_effect = ValueError("Invalid org_id")
        result = await server_module.list_projects(org_id="../../bad")
        assert "Error: Invalid org_id" == result


class TestGetProjectTool:
    @pytest.mark.asyncio
    async def test_returns_project(self, mock_client):
        mock_client.get_project.return_value = {
            "external_id": "proj1",
            "name": "Project",
            "pages": [{"external_id": "p1", "title": "Page 1"}],
        }
        result = await server_module.get_project("proj1")
        parsed = _parse(result)
        assert parsed["name"] == "Project"
        assert len(parsed["pages"]) == 1

    @pytest.mark.asyncio
    async def test_not_found(self, mock_client):
        mock_client.get_project.side_effect = HyperclastAPIError(404, "not_found", "Not found.")
        result = await server_module.get_project("nonexistent")
        assert "Error: Not found." == result

    @pytest.mark.asyncio
    async def test_validation_error_returns_message(self, mock_client):
        mock_client.get_project.side_effect = ValueError("Invalid project_id")
        result = await server_module.get_project("../../bad")
        assert "Error:" in result


# -- Pages ------------------------------------------------------------------


class TestListPagesTool:
    @pytest.mark.asyncio
    async def test_passes_pagination(self, mock_client):
        mock_client.list_pages.return_value = {"items": [], "count": 0}
        await server_module.list_pages(limit=10, offset=5)
        mock_client.list_pages.assert_called_once_with(10, 5)

    @pytest.mark.asyncio
    async def test_default_pagination(self, mock_client):
        mock_client.list_pages.return_value = {"items": [], "count": 0}
        await server_module.list_pages()
        mock_client.list_pages.assert_called_once_with(100, 0)


class TestSearchPagesTool:
    @pytest.mark.asyncio
    async def test_returns_results(self, mock_client):
        mock_client.search_pages.return_value = {"pages": [{"external_id": "p1", "title": "Meeting Notes"}]}
        result = await server_module.search_pages("meeting")
        parsed = _parse(result)
        assert parsed["pages"][0]["title"] == "Meeting Notes"
        mock_client.search_pages.assert_called_once_with("meeting")


class TestGetPageTool:
    @pytest.mark.asyncio
    async def test_returns_page_with_content(self, mock_client):
        mock_client.get_page.return_value = {
            "external_id": "p1",
            "title": "My Page",
            "details": {"content": "# Hello\nWorld", "filetype": "md"},
        }
        result = await server_module.get_page("p1")
        parsed = _parse(result)
        assert parsed["title"] == "My Page"
        assert parsed["details"]["content"] == "# Hello\nWorld"

    @pytest.mark.asyncio
    async def test_validation_error_returns_message(self, mock_client):
        mock_client.get_page.side_effect = ValueError("Invalid page_id")
        result = await server_module.get_page("foo/bar")
        assert "Error:" in result


class TestCreatePageTool:
    @pytest.mark.asyncio
    async def test_create_with_content(self, mock_client):
        mock_client.create_page.return_value = {
            "external_id": "p1",
            "title": "New Page",
        }
        result = await server_module.create_page("proj1", "New Page", content="# Hi")
        parsed = _parse(result)
        assert parsed["title"] == "New Page"
        mock_client.create_page.assert_called_once_with("proj1", "New Page", "# Hi")

    @pytest.mark.asyncio
    async def test_create_without_content(self, mock_client):
        mock_client.create_page.return_value = {"external_id": "p1", "title": "Empty"}
        await server_module.create_page("proj1", "Empty")
        mock_client.create_page.assert_called_once_with("proj1", "Empty", None)

    @pytest.mark.asyncio
    async def test_permission_denied(self, mock_client):
        mock_client.create_page.side_effect = HyperclastAPIError(403, "forbidden", "Permission denied.")
        result = await server_module.create_page("proj1", "Page")
        assert "Error: Permission denied." == result

    @pytest.mark.asyncio
    async def test_validation_error_returns_message(self, mock_client):
        mock_client.create_page.side_effect = ValueError("Invalid project_id")
        result = await server_module.create_page("bad!id", "Page")
        assert "Error:" in result


class TestUpdatePageTool:
    @pytest.mark.asyncio
    async def test_update_all_fields(self, mock_client):
        mock_client.update_page.return_value = {
            "external_id": "p1",
            "title": "Updated",
        }
        await server_module.update_page("p1", title="Updated", content="new", mode="overwrite")
        mock_client.update_page.assert_called_once_with("p1", "Updated", "new", "overwrite")

    @pytest.mark.asyncio
    async def test_default_mode_is_append(self, mock_client):
        mock_client.update_page.return_value = {"external_id": "p1", "title": "T"}
        await server_module.update_page("p1", content="added")
        mock_client.update_page.assert_called_once_with("p1", None, "added", "append")

    @pytest.mark.asyncio
    async def test_validation_error_returns_message(self, mock_client):
        mock_client.update_page.side_effect = ValueError("Invalid mode")
        result = await server_module.update_page("p1", title="T", mode="drop_table")
        assert "Error:" in result


class TestDeletePageTool:
    @pytest.mark.asyncio
    async def test_success(self, mock_client):
        mock_client.delete_page.return_value = None
        result = await server_module.delete_page("p1")
        assert result == "Page deleted."
        mock_client.delete_page.assert_called_once_with("p1")

    @pytest.mark.asyncio
    async def test_not_creator(self, mock_client):
        mock_client.delete_page.side_effect = HyperclastAPIError(403, "forbidden", "Permission denied.")
        result = await server_module.delete_page("p1")
        assert "Error: Permission denied." == result

    @pytest.mark.asyncio
    async def test_validation_error_returns_message(self, mock_client):
        mock_client.delete_page.side_effect = ValueError("Invalid page_id")
        result = await server_module.delete_page("../bad")
        assert "Error:" in result


# -- Shutdown ---------------------------------------------------------------


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_closes_client(self):
        client = AsyncMock()
        server_module._client = client
        await server_module._shutdown_client()
        client.close.assert_called_once()
        assert server_module._client is None

    @pytest.mark.asyncio
    async def test_shutdown_noop_when_no_client(self):
        server_module._client = None
        await server_module._shutdown_client()  # should not raise
        assert server_module._client is None
