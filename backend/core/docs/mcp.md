# MCP Server

The Hyperclast MCP server lets AI assistants read and write your pages directly. It implements the [Model Context Protocol](https://modelcontextprotocol.io/) and works with any MCP-compatible client, including Claude Code and Claude Desktop.

## Quick Start

### 1. Get an access token

Go to **Settings → Tokens** in Hyperclast, or use the CLI:

```bash
hyperclast token
```

### 2. Add the server to your client

**Claude Code:**

```bash
claude mcp add hyperclast -e HYPERCLAST_TOKEN=<ACCESS_TOKEN> -- uvx hyperclast-mcp
```

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hyperclast": {
      "command": "uvx",
      "args": ["hyperclast-mcp"],
      "env": {
        "HYPERCLAST_TOKEN": "<ACCESS_TOKEN>"
      }
    }
  }
}
```

That's it. Your AI assistant can now list projects, search pages, read content, and create or update pages on your behalf.

---

## Available Tools

| Tool            | Description                                                      |
| --------------- | ---------------------------------------------------------------- |
| `list_orgs`     | List your organizations                                          |
| `list_projects` | List projects, optionally including their pages                  |
| `get_project`   | Get a project with its pages, folders, and files                 |
| `list_pages`    | List pages (paginated)                                           |
| `search_pages`  | Search pages by title                                            |
| `get_page`      | Get a page's full content                                        |
| `create_page`   | Create a new page in a project                                   |
| `update_page`   | Update a page's title or content (append, prepend, or overwrite) |
| `delete_page`   | Delete a page                                                    |

---

## Configuration

| Variable           | Required | Default                  | Description                                                |
| ------------------ | -------- | ------------------------ | ---------------------------------------------------------- |
| `HYPERCLAST_TOKEN` | Yes      | —                        | Your API access token                                      |
| `HYPERCLAST_URL`   | No       | `https://hyperclast.com` | Base URL (set this for self-hosted or local dev instances) |

---

## Example Usage

Once the server is connected, you can ask your AI assistant things like:

- "List my projects in Hyperclast"
- "Search for pages about onboarding"
- "Create a new page in Project X with today's meeting notes"
- "Append a summary to the Q1 planning page"
- "Read the contents of my design spec"

The assistant will use the appropriate MCP tools automatically.

---

## Running from Source

If you want to run the server from a local checkout instead of installing from PyPI:

```bash
claude mcp add hyperclast \
  -e HYPERCLAST_TOKEN=<ACCESS_TOKEN> \
  -e HYPERCLAST_URL=http://localhost:9800 \
  -- uv run --directory /path/to/mcp hyperclast-mcp
```

---

## Development

```bash
cd mcp
uv sync
uv run hyperclast-mcp

# Run tests
uv run pytest tests/ -v

# Interactive testing with the MCP Inspector
npx @modelcontextprotocol/inspector uv run hyperclast-mcp
```
