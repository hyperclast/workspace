# Comments

Leave feedback on specific text ranges within pages. Supports threaded replies and AI persona reviews.

## Access Control

| Operation     | Permission                               |
| ------------- | ---------------------------------------- |
| View comments | Anyone with read access to the page      |
| Create/reply  | Editors only (`editor` role at any tier) |
| Edit body     | Comment author only                      |
| Delete human  | Comment author only                      |
| Delete AI     | Any editor on the page                   |
| AI review     | Editors only                             |

---

## List Comments

Get all comments for a page, with nested replies.

|              |                                         |
| ------------ | --------------------------------------- |
| **Endpoint** | `GET /api/v1/pages/{page_id}/comments/` |
| **Auth**     | Bearer token                            |

**Query Parameters:**

| Param    | Default | Description                      |
| -------- | ------- | -------------------------------- |
| `limit`  | 100     | Root comments per page (max 100) |
| `offset` | 0       | Root comments to skip            |

**Response (200):**

```json
{
  "items": [
    {
      "external_id": "Abc123XyZ",
      "parent_id": null,
      "author": {
        "external_id": "usr_xyz",
        "email": "alice@example.com",
        "display_name": "Alice Smith"
      },
      "ai_persona": "",
      "requester": null,
      "body": "This section seems unclear.",
      "anchor_from_b64": "AQ3s...",
      "anchor_to_b64": "AQ4t...",
      "anchor_text": "the highlighted passage",
      "created": "2026-03-18T10:00:00Z",
      "modified": "2026-03-18T10:00:00Z",
      "replies": []
    }
  ],
  "count": 1
}
```

| Field             | Description                                                              |
| ----------------- | ------------------------------------------------------------------------ |
| `ai_persona`      | Empty for human comments, or `socrates` / `einstein` / `dewey`           |
| `requester`       | User who triggered AI review (null for human comments)                   |
| `anchor_from_b64` | Base64 Yjs RelativePosition (start). Null if pending deferred resolution |
| `anchor_to_b64`   | Base64 Yjs RelativePosition (end)                                        |
| `anchor_text`     | Plain text snapshot of the highlighted range                             |
| `replies`         | Nested array of reply comments (same schema, no further nesting)         |

---

## Create Comment

|              |                                          |
| ------------ | ---------------------------------------- |
| **Endpoint** | `POST /api/v1/pages/{page_id}/comments/` |
| **Auth**     | Bearer token (editor)                    |

| Field             | Type   | Required? | Description                               |
| ----------------- | ------ | --------- | ----------------------------------------- |
| `body`            | string | Yes       | Comment body (markdown)                   |
| `anchor_text`     | string | Root only | Highlighted text                          |
| `anchor_from_b64` | string | No        | Base64 Yjs RelativePosition (start)       |
| `anchor_to_b64`   | string | No        | Base64 Yjs RelativePosition (end)         |
| `parent_id`       | string | No        | External ID of root comment (for replies) |

**Response (201):** The created comment object.

**Notes:**

- Root comments require `anchor_text`
- Replies set `parent_id` to a root comment's external ID
- Replies cannot have anchors (they inherit parent's anchor)
- Threading is one level deep — replies to replies are rejected

---

## Update Comment

|              |                                                        |
| ------------ | ------------------------------------------------------ |
| **Endpoint** | `PATCH /api/v1/pages/{page_id}/comments/{comment_id}/` |
| **Auth**     | Bearer token                                           |

| Field             | Type   | Required? | Description                      |
| ----------------- | ------ | --------- | -------------------------------- |
| `body`            | string | No        | Updated body (author only)       |
| `anchor_from_b64` | string | No        | Set anchor (deferred resolution) |
| `anchor_to_b64`   | string | No        | Set anchor (deferred resolution) |

**Response (200):** Updated comment object.

**Notes:**

- Body edits: author only
- Anchor setting: any client can set anchors on comments with null anchors (first-write-wins)
- Once anchors are set, they are immutable

---

## Delete Comment

|              |                                                         |
| ------------ | ------------------------------------------------------- |
| **Endpoint** | `DELETE /api/v1/pages/{page_id}/comments/{comment_id}/` |
| **Auth**     | Bearer token                                            |

**Response (204):** No content.

**Notes:**

- Deleting a root comment cascades to all replies
- Human comments: author only
- AI comments: any editor

---

## Trigger AI Review

Start an AI persona review of a page. Comments are created asynchronously.

|              |                                                    |
| ------------ | -------------------------------------------------- |
| **Endpoint** | `POST /api/v1/pages/{page_id}/comments/ai-review/` |
| **Auth**     | Bearer token (editor)                              |

| Field     | Type   | Required? | Description                        |
| --------- | ------ | --------- | ---------------------------------- |
| `persona` | string | Yes       | `socrates`, `einstein`, or `dewey` |

**Response (202):**

```json
{
  "status": "queued",
  "message": "Socrates is reviewing your page..."
}
```

**AI Personas:**

| Persona    | Behavior                                     |
| ---------- | -------------------------------------------- |
| `socrates` | Asks clarifying questions about your text    |
| `einstein` | Surfaces insights, patterns, and connections |
| `dewey`    | Suggests external resources and references   |

**Error Responses:**

- **400** - Invalid persona
- **409** - Review already in progress for this persona on this page

---

## Examples

### List comments

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"

curl "$BASE_URL/api/v1/pages/$PAGE_ID/comments/" \
  -H "Authorization: Bearer $TOKEN"
```

### Add a comment

```bash
curl -X POST "$BASE_URL/api/v1/pages/$PAGE_ID/comments/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body": "This needs more detail.", "anchor_text": "the relevant passage"}'
```

### Trigger AI review

```bash
curl -X POST "$BASE_URL/api/v1/pages/$PAGE_ID/comments/ai-review/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"persona": "socrates"}'
```
