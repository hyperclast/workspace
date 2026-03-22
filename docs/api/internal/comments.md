# Comments API

## Table of Contents

- [List comments](#list-comments)
- [List replies](#list-replies)
- [Create comment](#create-comment)
- [Update comment](#update-comment)
- [Delete comment](#delete-comment)
- [Trigger AI review](#trigger-ai-review)

## List comments

Retrieve comments for a page, with nested replies.

### URL

`/api/v1/pages/{external_id}/comments/`

### HTTP Method

`GET`

### Path Params

| Parameter     | Type   | Description        |
| ------------- | ------ | ------------------ |
| `external_id` | string | Page's external ID |

### Query Params

| Parameter       | Type | Default | Description                     |
| --------------- | ---- | ------- | ------------------------------- |
| `limit`         | int  | 100     | Max root comments (max 100)     |
| `offset`        | int  | 0       | Number of root comments to skip |
| `replies_limit` | int  | 20      | Max replies per root (max 50)   |

### Authorization

Requires `user_can_access_page()` — anyone who can read the page can see comments.

### Response

- Status Code: 200
- Schema:

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
      "replies_count": 1,
      "replies": [
        {
          "external_id": "Def456Abc",
          "parent_id": "Abc123XyZ",
          "author": { "external_id": "usr_abc", "email": "bob@example.com", "display_name": "Bob" },
          "ai_persona": "",
          "requester": null,
          "body": "Agreed, I'll rewrite this part.",
          "anchor_from_b64": null,
          "anchor_to_b64": null,
          "anchor_text": "",
          "created": "2026-03-18T10:05:00Z",
          "modified": "2026-03-18T10:05:00Z",
          "replies": []
        }
      ]
    }
  ],
  "count": 1
}
```

**Notes:**

- Root comments are paginated. Replies are nested inline; only the first `replies_limit` replies are returned per root. Use [List replies](#list-replies) to load more.
- Sorted by `created` ascending.
- `anchor_from_b64` / `anchor_to_b64` are base64-encoded Yjs RelativePositions. May be null for AI comments pending deferred resolution.
- `anchor_text` is a plain text snapshot of the highlighted range.
- `ai_persona` is empty for human comments, or one of: `socrates`, `einstein`, `dewey`.
- `requester` is set for AI comments (the user who triggered the review), null for human comments.
- `replies_count` is the total number of replies for root comments; use it to show "Load more replies (X more)".

---

## List replies

Load additional replies for a root comment (pagination).

### URL

`/api/v1/pages/{external_id}/comments/{comment_id}/replies/`

### HTTP Method

`GET`

### Path Params

| Parameter     | Type   | Description                |
| ------------- | ------ | -------------------------- |
| `external_id` | string | Page's external ID         |
| `comment_id`  | string | Root comment's external ID |

### Query Params

| Parameter | Type | Default | Description                    |
| --------- | ---- | ------- | ------------------------------ |
| `limit`   | int  | 20      | Max replies to return (max 50) |
| `offset`  | int  | 0       | Number of replies to skip      |

### Authorization

Requires `user_can_access_page()` — anyone who can read the page can list replies.

### Response

- Status Code: 200
- Schema:

```json
{
  "items": [
    {
      "external_id": "Def456Abc",
      "parent_id": "Abc123XyZ",
      "author": { "external_id": "usr_abc", "email": "bob@example.com", "display_name": "Bob" },
      "ai_persona": "",
      "requester": null,
      "body": "Agreed, I'll rewrite this part.",
      "anchor_from_b64": null,
      "anchor_to_b64": null,
      "anchor_text": "",
      "created": "2026-03-18T10:05:00Z",
      "modified": "2026-03-18T10:05:00Z",
      "replies": [],
      "replies_count": 0
    }
  ],
  "count": 15
}
```

### Error Responses

| Status | Condition                      |
| ------ | ------------------------------ |
| 404    | Page or root comment not found |

---

## Create comment

Create a root comment or reply on a page.

### URL

`/api/v1/pages/{external_id}/comments/`

### HTTP Method

`POST`

### Authorization

Requires `user_can_edit_in_page()` — editors only.

### Request Body

| Field             | Type   | Required | Description                                                                    |
| ----------------- | ------ | -------- | ------------------------------------------------------------------------------ |
| `body`            | string | Yes      | Comment body (markdown)                                                        |
| `parent_id`       | string | No       | External ID of root comment (for replies), null for root                       |
| `anchor_from_b64` | string | No       | Base64 Yjs RelativePosition (start). Required for root, forbidden for replies. |
| `anchor_to_b64`   | string | No       | Base64 Yjs RelativePosition (end). Required for root, forbidden for replies.   |
| `anchor_text`     | string | No       | Highlighted text. Required for root comments.                                  |

### Response

- Status Code: 201
- Schema: Same as a single comment in the list response.

### Error Responses

| Status | Condition                                                           |
| ------ | ------------------------------------------------------------------- |
| 400    | Empty body, missing anchor on root, anchor on reply, reply-to-reply |
| 403    | User is not an editor                                               |
| 404    | Page or parent comment not found                                    |

---

## Update comment

Edit a comment's body or set anchors (deferred resolution).

### URL

`/api/v1/pages/{external_id}/comments/{comment_id}/`

### HTTP Method

`PATCH`

### Authorization

- **Body edit**: Author of the comment only.
- **Anchor setting**: Any client can set anchors on a comment that has null `anchor_from`/`anchor_to` (first-write-wins for deferred resolution).

### Request Body

| Field             | Type   | Required | Description                 |
| ----------------- | ------ | -------- | --------------------------- |
| `body`            | string | No       | Updated comment body        |
| `anchor_from_b64` | string | No       | Base64 Yjs RelativePosition |
| `anchor_to_b64`   | string | No       | Base64 Yjs RelativePosition |

### Response

- Status Code: 200
- Schema: Updated comment object.

### Error Responses

| Status | Condition                      |
| ------ | ------------------------------ |
| 400    | Empty body, anchor on reply    |
| 403    | Non-author trying to edit body |
| 404    | Comment not found              |

---

## Delete comment

Delete a comment. Deleting a root comment cascades to all replies.

### URL

`/api/v1/pages/{external_id}/comments/{comment_id}/`

### HTTP Method

`DELETE`

### Authorization

- **Human comments**: Author only.
- **AI comments**: Any editor on the page.

### Response

- Status Code: 204

### Error Responses

| Status | Condition                |
| ------ | ------------------------ |
| 403    | Not authorized to delete |
| 404    | Comment not found        |

---

## Trigger AI review

Start an AI persona review of a page. Comments are created asynchronously via RQ job.

### URL

`/api/v1/pages/{external_id}/comments/ai-review/`

### HTTP Method

`POST`

### Authorization

Requires `user_can_edit_in_page()` — editors only.

### Request Body

| Field     | Type   | Required | Description                                    |
| --------- | ------ | -------- | ---------------------------------------------- |
| `persona` | string | Yes      | AI persona: `socrates`, `einstein`, or `dewey` |

### Response

- Status Code: 202
- Schema:

```json
{
  "status": "queued",
  "message": "Socrates is reviewing your page..."
}
```

### Error Responses

| Status | Condition                                      |
| ------ | ---------------------------------------------- |
| 400    | Invalid persona                                |
| 403    | User is not an editor                          |
| 404    | Page not found                                 |
| 409    | AI review already in progress for this persona |

### Notes

- The endpoint syncs `Page.details['content']` from the latest Yjs snapshot synchronously before enqueuing the job.
- AI comments are created with `anchor_text` only (no binary anchors). The frontend resolves them to Yjs RelativePositions via deferred resolution.
- Comments are broadcast via WebSocket (`comments_updated` message) as they are created.

---
