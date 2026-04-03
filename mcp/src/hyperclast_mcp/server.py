"""Hyperclast MCP server — tools for AI assistants to interact with Hyperclast."""

from __future__ import annotations

import json
from typing import Any, Literal

import click
from mcp.server.fastmcp import FastMCP

from .client import HyperclastAPIError, HyperclastClient, UpdateMode
from .config import get_base_url, get_token

mcp = FastMCP(
    "Hyperclast",
    instructions=(
        "Hyperclast is a collaborative note-taking and document management app. "
        "Use these tools to list orgs/projects, search pages, read page content, "
        "and create or update pages on behalf of the user."
    ),
)

_client: HyperclastClient | None = None


def _get_client() -> HyperclastClient:
    global _client
    if _client is None:
        _client = HyperclastClient(get_base_url(), get_token())
    return _client


async def _shutdown_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def _format_error(e: HyperclastAPIError | ValueError) -> str:
    return f"Error: {e.message}" if isinstance(e, HyperclastAPIError) else f"Error: {e}"


def _pretty(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


# -- Orgs ------------------------------------------------------------------


@mcp.tool()
async def list_orgs() -> str:
    """List the user's organizations.

    Returns a list of orgs with their id, name, and plan status.
    """
    try:
        orgs = await _get_client().list_orgs()
        return _pretty(orgs)
    except HyperclastAPIError as e:
        return _format_error(e)


# -- Projects ---------------------------------------------------------------


@mcp.tool()
async def list_projects(
    org_id: str | None = None,
    include_pages: bool = False,
) -> str:
    """List projects the user has access to.

    Args:
        org_id: Filter by organization id (optional).
        include_pages: If true, include each project's pages and folders.
    """
    try:
        projects = await _get_client().list_projects(org_id, include_pages)
        return _pretty(projects)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def get_project(project_id: str) -> str:
    """Get a project with its pages, folders, and files.

    Args:
        project_id: The project's external id.
    """
    try:
        project = await _get_client().get_project(project_id)
        return _pretty(project)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def create_project(
    org_id: str,
    name: str,
    description: str | None = None,
) -> str:
    """Create a new project in an organization.

    Args:
        org_id: The organization to create the project in.
        name: Project name (1-255 characters).
        description: Optional project description.
    """
    try:
        project = await _get_client().create_project(org_id, name, description)
        return _pretty(project)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def update_project(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
) -> str:
    """Update a project's name or description.

    Args:
        project_id: The project's external id.
        name: New name (optional, 1-255 characters).
        description: New description (optional).
    """
    try:
        project = await _get_client().update_project(project_id, name, description)
        return _pretty(project)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def delete_project(
    project_id: str,
    confirm: bool = False,
) -> str:
    """Delete a project and ALL its pages (creator only, soft-delete).

    THIS IS DESTRUCTIVE — every page in the project becomes inaccessible.
    The user must explicitly ask for deletion before calling this tool.

    Args:
        project_id: The project's external id.
        confirm: Must be true to proceed. Prevents accidental deletion.
    """
    if not confirm:
        return "Error: confirm must be true. This will delete the project and ALL its pages."
    try:
        await _get_client().delete_project(project_id)
        return "Project deleted."
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


# -- Pages ------------------------------------------------------------------


@mcp.tool()
async def list_pages(limit: int = 100, offset: int = 0) -> str:
    """List pages with pagination.

    Args:
        limit: Maximum number of pages to return (1-100, default 100).
        offset: Number of pages to skip (default 0).
    """
    try:
        result = await _get_client().list_pages(limit, offset)
        return _pretty(result)
    except HyperclastAPIError as e:
        return _format_error(e)


@mcp.tool()
async def search_pages(query: str) -> str:
    """Search pages by title.

    Args:
        query: Search query string to match against page titles.
    """
    try:
        result = await _get_client().search_pages(query)
        return _pretty(result)
    except HyperclastAPIError as e:
        return _format_error(e)


@mcp.tool()
async def get_page(page_id: str) -> str:
    """Get a page with its full content.

    Args:
        page_id: The page's external id.
    """
    try:
        page = await _get_client().get_page(page_id)
        return _pretty(page)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def create_page(
    project_id: str,
    title: str,
    content: str | None = None,
) -> str:
    """Create a new page in a project.

    Args:
        project_id: The project to create the page in.
        title: Page title (1-100 characters).
        content: Optional markdown content for the page.
    """
    try:
        page = await _get_client().create_page(project_id, title, content)
        return _pretty(page)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def update_page(
    page_id: str,
    title: str | None = None,
    content: str | None = None,
    mode: UpdateMode = "append",
) -> str:
    """Update a page's title or content.

    Args:
        page_id: The page's external id.
        title: New title (optional, keeps current title if omitted).
        content: New content (optional). How it's applied depends on mode.
        mode: How to apply content — "append" (default) adds to end,
              "prepend" adds to beginning, "overwrite" replaces everything.
    """
    try:
        page = await _get_client().update_page(page_id, title, content, mode)
        return _pretty(page)
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


@mcp.tool()
async def delete_page(page_id: str) -> str:
    """Delete a page (creator only).

    Args:
        page_id: The page's external id.
    """
    try:
        await _get_client().delete_page(page_id)
        return "Page deleted."
    except (HyperclastAPIError, ValueError) as e:
        return _format_error(e)


# -- CLI entry point --------------------------------------------------------


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio"]),
    default="stdio",
    help="MCP transport (default: stdio).",
)
def main(transport: str) -> None:
    """Run the Hyperclast MCP server."""
    # Validate config eagerly so the user sees errors immediately.
    get_token()
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
