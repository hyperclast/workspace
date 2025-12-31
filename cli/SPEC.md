# Hyperclast CLI Specification

This document captures the design decisions for the Hyperclast CLI. It serves as the source of truth for CLI behavior and can be iterated on before implementation changes.

## Design Principles

1. **Explicit over implicit** - Commands clearly state what they do; no magic behavior
2. **Resource-action pattern** - `hyperclast <resource> <action>` (like `gh`, `kubectl`)
3. **Sensible defaults** - Set a default project once, use it everywhere
4. **Unix-friendly** - Stdin/stdout piping, JSON output option, composable
5. **Helpful errors** - Error messages suggest next steps
6. **No short flags** - Prefer explicit, discoverable long flags only

## Command Structure

```
hyperclast <resource> <action> [flags]
```

No command aliases or short flags for now - prefer explicit, discoverable commands.

---

## Authentication

### `hyperclast auth login`

Prompts for API token with helpful instructions, validates against API, stores in config.

```
$ hyperclast auth login

To authenticate, you need an API token from Hyperclast.

  1. Open https://app.hyperclast.com/settings/api
  2. Copy your API token

Enter your API token: ████████
✓ Authenticated as alice@example.com
Config saved to /Users/alice/.config/hyperclast/config.yaml
```

**Behavior:**

- Shows URL where user can get their token
- Reads token from stdin (no echo for security in future)
- Validates token by calling `GET /api/users/me/`
- On success: saves token to config file
- On failure: shows error, does not save

### `hyperclast auth logout`

Removes stored token from config.

```
$ hyperclast auth logout
✓ Logged out successfully
```

### `hyperclast auth status`

Shows current authentication state.

```
$ hyperclast auth status
✓ Authenticated as alice@example.com
```

```
$ hyperclast auth status
Not authenticated. Run 'hyperclast auth login' to authenticate.
```

---

## Organizations

### `hyperclast org list`

Lists organizations the user belongs to.

```
$ hyperclast org list
ID              NAME           DOMAIN
org_abc123      Acme Corp      acme.com
org_def456      Personal       (default)
```

### `hyperclast org current`

Shows the current default organization.

```
$ hyperclast org current
Default organization: Personal (org_def456)
```

### `hyperclast org use <id>`

Sets the default organization.

```
$ hyperclast org use org_abc123
✓ Default organization set to "Acme Corp" (org_abc123)
```

**Validation:** Verifies org exists and user has access before saving.

---

## Projects

### `hyperclast project list`

Lists projects. Optionally filtered by org.

```
$ hyperclast project list
ID              NAME            ORG
proj_abc123     Work Notes      Acme Corp (default)
proj_def456     Personal        Personal

$ hyperclast project list --org org_abc123
ID              NAME            ORG
proj_abc123     Work Notes      Acme Corp
```

**Flags:**

- `--org <id>` - Filter by organization ID

### `hyperclast project current`

Shows the current default project.

```
$ hyperclast project current
Default project: Work Notes (proj_abc123)
```

### `hyperclast project use <id>`

Sets the default project.

```
$ hyperclast project use proj_abc123
✓ Default project set to "Work Notes" (proj_abc123)
```

**Validation:** Verifies project exists and user has access before saving.

---

## Pages

### `hyperclast page new`

Creates a new page from stdin or file.

```
$ cat build.log | hyperclast page new --project proj_abc --title "Build Log"
✓ Created page "Build Log" (page_xyz789)
  https://app.hyperclast.com/pages/page_xyz789/

$ echo "Quick note" | hyperclast page new --project proj_abc
✓ Created page "Dec 30, 2025 at 2:45 PM" (page_xyz789)
  https://app.hyperclast.com/pages/page_xyz789/
```

**Flags:**

- `--project <id>` - Project ID (uses default if not specified)
- `--title <string>` - Page title (defaults to friendly timestamp)
- `--file <path>` - Read content from file instead of stdin
- `--filetype <type>` - File type: `txt` (default), `md`, `csv`
- `--meta` - Append metadata backmatter to content
- `--source <string>` - Source description for metadata (e.g., "make build")

**Title Default Format:** `Jan 2, 2006 at 3:04 PM` (Go time format)

**Filetype:**

- Default is `txt` (plain text, no styling in editor)
- Use `--filetype md` for markdown rendering
- Future: `--filetype auto` for heuristic-based detection

**Metadata Backmatter:**

When `--meta` is specified, metadata is appended to the content:

```
$ make build 2>&1 | hyperclast page new --project proj_abc --meta --source "make build"
```

Creates page with content:

```
[actual build output here]

---
Captured by Hyperclast CLI
Source: make build
Time: 2025-12-30 14:45:00 UTC
Host: alice-macbook
Directory: /Users/alice/myproject
---
```

**Error Cases:**

```
# No project specified and no default set
$ echo "test" | hyperclast page new --title "Test"
Error: No project specified.
  Use --project <id> or set a default: hyperclast project use <id>
  Run 'hyperclast project list' to see available projects.

# No content provided (not piped, no --file)
$ hyperclast page new --project proj_abc --title "Empty"
Error: No content provided. Pipe content or use --file <path>

# Empty content
$ echo "" | hyperclast page new --project proj_abc --title "Empty"
Error: No content provided. Pipe content or use --file <path>
```

### `hyperclast page append <id>`

Appends content to the end of an existing page.

```
$ echo "New entry" | hyperclast page append page_xyz789
✓ Appended to page "Build Log" (page_xyz789)

$ cat more-logs.txt | hyperclast page append page_xyz789 --meta --source "tail -f logs"
✓ Appended to page "Build Log" (page_xyz789)
```

**Flags:**

- `--file <path>` - Read content from file instead of stdin
- `--meta` - Append metadata backmatter to content
- `--source <string>` - Source description for metadata

### `hyperclast page prepend <id>`

Prepends content to the beginning of an existing page.

```
$ echo "Header info" | hyperclast page prepend page_xyz789
✓ Prepended to page "Build Log" (page_xyz789)
```

**Flags:**

- `--file <path>` - Read content from file instead of stdin
- `--meta` - Append metadata backmatter to content
- `--source <string>` - Source description for metadata

### `hyperclast page overwrite <id>`

Replaces all content of an existing page.

```
$ cat updated-config.txt | hyperclast page overwrite page_xyz789
✓ Overwrote page "Config" (page_xyz789)
```

**Flags:**

- `--file <path>` - Read content from file instead of stdin
- `--meta` - Append metadata backmatter to content
- `--source <string>` - Source description for metadata

### `hyperclast page list`

Lists pages. Optionally filtered by project.

```
$ hyperclast page list
ID              TITLE                      UPDATED
page_abc123     Build Log                  Dec 30, 2025 2:45 PM
page_def456     Meeting Notes              Dec 29, 2025 10:30 AM

$ hyperclast page list --project proj_abc123
ID              TITLE                      UPDATED
page_abc123     Build Log                  Dec 30, 2025 2:45 PM
```

**Flags:**

- `--project <id>` - Filter by project ID

### `hyperclast page get <id>`

Outputs page content to stdout.

```
$ hyperclast page get page_abc123
# Build Log

Build started at 2025-12-30 14:45:00
...

$ hyperclast page get page_abc123 > backup.txt
```

**Behavior:**

- Outputs raw content only (no metadata)
- No trailing newline added if content doesn't have one
- Suitable for piping to other commands or redirecting to file

---

## Global Flags

| Flag                | Default                            | Description                       |
| ------------------- | ---------------------------------- | --------------------------------- |
| `--config <path>`   | `~/.config/hyperclast/config.yaml` | Config file path                  |
| `--api-url <url>`   | `https://hyperclast.com/api`       | API URL (for testing/self-hosted) |
| `--output <format>` | `text`                             | Output format: `text`, `json`     |
| `--quiet`           | `false`                            | Suppress info messages            |
| `--verbose`         | `false`                            | Show debug output                 |

### JSON Output

When `--output json` is specified, commands output JSON instead of formatted text.

```
$ hyperclast project list --output json
[
  {
    "external_id": "proj_abc123",
    "name": "Work Notes",
    "org": {"external_id": "org_abc123", "name": "Acme Corp"}
  }
]

$ hyperclast auth status --output json
{"authenticated": true, "email": "alice@example.com", "external_id": "user_abc123"}
```

### Quiet Mode

When `--quiet` is specified:

- Success messages (✓) are suppressed
- Info messages are suppressed
- Only essential output (data, errors) is shown

```
$ echo "test" | hyperclast page new --project proj_abc --title "Test" --quiet
page_xyz789
```

---

## Configuration

### File Location

Default: `~/.config/hyperclast/config.yaml`

Override with `--config` flag or `HYPERCLAST_CONFIG` environment variable.

### File Format

```yaml
api_url: https://hyperclast.com/api
token: hc_xxxxxxxxxxxxxxxx
defaults:
  org_id: org_abc123
  project_id: proj_xyz789
```

### Permissions

- Config directory created with `0700`
- Config file created with `0600`

---

## API Integration

### Authentication

All API requests use Bearer token authentication:

```
Authorization: Bearer <token>
```

### Endpoints Used

| Command                         | Method | Endpoint              |
| ------------------------------- | ------ | --------------------- |
| `auth login/status`             | GET    | `/api/users/me/`      |
| `org list`                      | GET    | `/api/orgs/`          |
| `project list`                  | GET    | `/api/projects/`      |
| `project get`                   | GET    | `/api/projects/{id}/` |
| `page list`                     | GET    | `/api/pages/`         |
| `page get`                      | GET    | `/api/pages/{id}/`    |
| `page new`                      | POST   | `/api/pages/`         |
| `page append/prepend/overwrite` | PUT    | `/api/pages/{id}/`    |

### Backend Changes Required

**POST /api/pages/ (create page):**

- Accept `filetype` in details (default: `txt`)

**PUT /api/pages/{id}/ (update page):**

- Accept `mode` parameter: `append` (default), `prepend`, `overwrite`
- If mode is `append`: concatenate new content after existing (default)
- If mode is `prepend`: concatenate new content before existing
- If mode is `overwrite`: replace existing content

### Error Handling

| HTTP Status | Behavior                                          |
| ----------- | ------------------------------------------------- |
| 401         | "authentication failed: invalid or expired token" |
| 403         | Show API error message                            |
| 404         | "not found" with context                          |
| 5xx         | "API error (500): ..."                            |

---

## Future Considerations

### Potential Commands (Not Yet Implemented)

```bash
# Delete page
hyperclast page delete <id>
hyperclast page delete <id> --force

# Create project
hyperclast project new "Project Name" --org org_abc

# Watch mode - re-run on file changes
hyperclast watch ./logs/ --project proj_abc

# Interactive mode
hyperclast interactive
```

### Potential Features

- **Shell completions** - `hyperclast completion bash/zsh/fish`
- **Token from environment** - `HYPERCLAST_TOKEN` env var
- **Multiple profiles** - `--profile work` for different accounts
- **Retry logic** - Automatic retry on transient failures
- **Progress indicator** - For large file uploads
- **Version command** - `hyperclast version`
- **Auto filetype detection** - `--filetype auto` with heuristics

---

## Open Questions

1. ~~Should `page new` support `--filetype` flag for non-markdown content?~~ **Yes, default txt**
2. ~~Should there be a `hyperclast pipe` shorthand for `page new`?~~ **No, use explicit commands**
3. Should we support reading token from environment variable?
4. What should happen if stdin is a TTY but no `--file` is provided - wait for input or error?

---

## Changelog

### v0.1.0 (Initial)

- `auth login` (with URL hint), `auth logout`, `auth status`
- `org list`, `org current`, `org use`
- `project list`, `project current`, `project use`
- `page new`, `page append`, `page prepend`, `page overwrite`
- `page list`, `page get`
- Config file support
- JSON output mode
- `--filetype` flag (default: txt)
- `--meta` and `--source` flags for backmatter metadata
