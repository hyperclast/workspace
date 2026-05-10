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
| `delete_page`    | Delete a page (requires `confirm`, creator only)     |

## Live propagation & consistency

`create_page` and `update_page` (content modes) propagate to any open
editor for the page **live** — the user sees Claude's edit appear in
their CodeMirror without a refresh — and the change **survives a
reload**. The flow: the REST handler saves the page row and enqueues
an `apply_text_update_to_page` job on the `internal` queue (wrapped in
`transaction.on_commit` so DB write and queue enqueue go together). A
worker hydrates the room's Yjs CRDT, applies the mutation, persists
the resulting update to `y_updates`, and broadcasts to connected
WebSocket consumers.

This is **eventually consistent**: there is a sub-second window
between `update_page` returning HTTP 200 and the worker draining the
job. If the worker is delayed (queue depth, Redis blip), the API call
has already returned but the editor has not yet seen the change. The
permission re-check at execution time also means a write can be
silently dropped if the user lost edit access between enqueue and
execute (logged as `mcp_text_update result=denied` server-side, but
the original API response was already 200). For interactive AI edits
this window is invisible; for scripts that rely on read-after-write
consistency, fetch via `get_page` after the write.

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
