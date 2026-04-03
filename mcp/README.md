# Hyperclast MCP Server

[MCP](https://modelcontextprotocol.io/) server for [Hyperclast](https://hyperclast.com). Exposes orgs, projects, and pages to AI assistants.

## Tools

| Tool             | Description                                          |
| ---------------- | ---------------------------------------------------- |
| `list_orgs`      | List organizations                                   |
| `list_projects`  | List projects, optionally with pages                 |
| `get_project`    | Get a project with pages, folders, and files         |
| `create_project` | Create a project in an organization                  |
| `update_project` | Update a project's name or description               |
| `delete_project` | Delete a project (requires `confirm`, creator only)  |
| `list_pages`     | List pages (paginated)                               |
| `search_pages`   | Search pages by title                                |
| `get_page`       | Get page content                                     |
| `create_page`    | Create a page in a project                           |
| `update_page`    | Update title/content (append, prepend, or overwrite) |
| `delete_page`    | Delete a page                                        |

## Setup

### 1. Get an access token

**Settings → Tokens** in Hyperclast, or via CLI: `hyperclast token`.

### 2. Add the server

**Claude Code:**

```bash
claude mcp add hyperclast -e HYPERCLAST_TOKEN=your-token-here -- uvx hyperclast-mcp
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hyperclast": {
      "command": "uvx",
      "args": ["hyperclast-mcp"],
      "env": {
        "HYPERCLAST_TOKEN": "your-token-here"
      }
    }
  }
}
```

For local dev, add `-e HYPERCLAST_URL=http://localhost:9800` or put it in the `env` object.

### Run from source

```bash
claude mcp add hyperclast \
  -e HYPERCLAST_TOKEN=your-token-here \
  -e HYPERCLAST_URL=http://localhost:9800 \
  -- uv run --directory /path/to/mcp hyperclast-mcp
```

## Configuration

| Variable           | Required | Default                  | Description  |
| ------------------ | -------- | ------------------------ | ------------ |
| `HYPERCLAST_TOKEN` | Yes      | —                        | Access token |
| `HYPERCLAST_URL`   | No       | `https://hyperclast.com` | Base URL     |

## Development

```bash
cd mcp
uv sync
uv run hyperclast-mcp
uv run pytest tests/ -v

# Interactive testing
npx @modelcontextprotocol/inspector uv run hyperclast-mcp
```
