# Mentions

The Mentions API allows you to retrieve pages where the current user is @mentioned.

---

## Get My Mentions

Retrieve all pages where you are @mentioned.

|              |                      |
| ------------ | -------------------- |
| **Endpoint** | `GET /api/mentions/` |
| **Auth**     | Bearer token         |

**Query Parameters:**

| Parameter | Type | Default | Description               |
| --------- | ---- | ------- | ------------------------- |
| `limit`   | int  | 50      | Maximum number of results |
| `offset`  | int  | 0       | Number of results to skip |

**Response (200):**

```json
{
  "mentions": [
    {
      "page_external_id": "abc123",
      "page_title": "Meeting Notes",
      "project_name": "Research",
      "modified": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "has_more": false
}
```

**Notes:**

- Only returns mentions from pages the user has access to
- Mentions from pages where access has been revoked are not included
- Results are ordered by page modified date (most recent first)
- Mentions use the format `@[Username](@user_id)` in page content

---

## Mention Format

Mentions in page content follow this format:

```markdown
Hey @[Alice](@user123) can you take a look?
```

| Part         | Description                                     |
| ------------ | ----------------------------------------------- |
| `@`          | Mention prefix                                  |
| `[Alice]`    | Display text (username)                         |
| `(@user123)` | User's external ID with `@` prefix (not a link) |

The `@` prefix inside the parentheses distinguishes mentions from regular markdown links.

Use the [org members autocomplete](/dev/api/orgs#autocomplete-members) endpoint to get user IDs for mention insertion.
