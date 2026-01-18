# Mentions API

## Table of Contents

- [Get my mentions](#get-my-mentions)

## Get my mentions

Retrieve all pages where the authenticated user is @mentioned.

### URL

`/api/mentions/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

| Parameter | Type | Default | Description               |
| --------- | ---- | ------- | ------------------------- |
| `limit`   | int  | 50      | Maximum number of results |
| `offset`  | int  | 0       | Number of results to skip |

### Data Params

None

### Authorization

Requires authentication. See [Overview](./overview.md) for details on session-based authentication.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "mentions": [
    {
      "page_external_id": "abc123",
      "page_title": "Meeting Notes",
      "project_name": "Research Project",
      "modified": "2025-01-15T10:30:00Z"
    },
    {
      "page_external_id": "def456",
      "page_title": "Task List",
      "project_name": "Engineering",
      "modified": "2025-01-14T09:00:00Z"
    }
  ],
  "total": 2,
  "has_more": false
}
```

**Notes:**

- Returns pages where the current user is @mentioned
- **Only returns mentions from pages the user has access to** (access control enforced)
- Mentions from pages where access has been revoked are filtered out
- Only returns mentions from non-deleted pages in non-deleted projects
- Results are ordered by page modified date (most recent first)
- The `project_name` field shows which project the page belongs to
- Mentions are tracked via the `@[Username](@user_id)` format in page content
- Mentions are synced when pages are saved via the collaboration system

**Mention Format:**

Mentions in page content use the format `@[Username](@user_external_id)`:

```markdown
Hey @[Alice](@user123) can you review this?
```

The `@` prefix inside the parentheses distinguishes mentions from regular markdown links.

This format allows:

- Display text (username) to be shown in the editor
- User ID for reliable linking even if username changes
- Autocomplete via the org members endpoint

**Example Usage:**

```bash
# Get first 50 mentions
GET /api/mentions/

# Get mentions with pagination
GET /api/mentions/?limit=20&offset=40
```

---
