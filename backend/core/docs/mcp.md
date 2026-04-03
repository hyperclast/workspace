# MCP Server

The Hyperclast MCP server lets AI assistants read and write your pages directly. It implements the [Model Context Protocol](https://modelcontextprotocol.io/) and works with any MCP-compatible client, including Claude Code and Claude Desktop.

## Setup

<div class="client-tabs">
  <div class="client-tab-bar">
    <button class="client-tab active" data-tab="claude-code">Claude Code</button>
    <button class="client-tab" data-tab="claude-desktop">Claude Desktop</button>
  </div>
  <div class="client-tab-panel active" data-tab="claude-code">

```bash
claude mcp add hyperclast \
  -e HYPERCLAST_TOKEN=<ACCESS_TOKEN> \
  -- uvx hyperclast-mcp
```

  </div>
  <div class="client-tab-panel" data-tab="claude-desktop">

Add to `claude_desktop_config.json`:

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

  </div>
</div>

That's it. Your AI assistant can now manage projects, search pages, read content, and create or update pages on your behalf.

---

## Available Tools

| Tool             | Description                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `list_orgs`      | List your organizations                                          |
| `list_projects`  | List projects, optionally including their pages                  |
| `get_project`    | Get a project with its pages, folders, and files                 |
| `create_project` | Create a new project in an organization                          |
| `update_project` | Update a project's name or description                           |
| `delete_project` | Delete a project (requires confirmation, creator only)           |
| `list_pages`     | List pages (paginated)                                           |
| `search_pages`   | Search pages by title                                            |
| `get_page`       | Get a page's full content                                        |
| `create_page`    | Create a new page in a project                                   |
| `update_page`    | Update a page's title or content (append, prepend, or overwrite) |
| `delete_page`    | Delete a page                                                    |

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
