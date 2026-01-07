# Overview

The Hyperclast API provides programmatic access to your pages, projects, and organizations.

## Base URL

All API endpoints are relative to:

```
<BASE_URL>/api/
```

---

## Authentication

All requests require a bearer token in the `Authorization` header:

```
Authorization: Bearer <ACCESS_TOKEN>
```

**Getting your token:**

1. Log in to the web app
2. Go to **Settings**
3. Copy your token from the "Developer" section

**Example request:**

```bash
curl -H "Authorization: Bearer <ACCESS_TOKEN>" \
     <BASE_URL>/api/pages/
```

---

## Request Format

Include these headers with all requests:

| Header          | Value                   |
| --------------- | ----------------------- |
| `Authorization` | `Bearer <ACCESS_TOKEN>` |
| `Content-Type`  | `application/json`      |

---

## Response Format

### Success

| Status | Meaning             |
| ------ | ------------------- |
| 200    | Success             |
| 201    | Created             |
| 204    | No content (delete) |

**Single resource:**

```json
{
  "external_id": "abc123",
  "title": "My Page",
  "created": "2025-01-15T10:30:00Z"
}
```

**List (paginated):**

```json
{
  "items": [...],
  "count": 42
}
```

### Errors

| Status | Meaning           |
| ------ | ----------------- |
| 400    | Bad request       |
| 401    | Not authenticated |
| 403    | Permission denied |
| 404    | Not found         |
| 422    | Validation error  |

**Error format:**

```json
{ "message": "Error description" }
```

---

## Pagination

List endpoints support pagination:

| Param    | Default | Max | Description    |
| -------- | ------- | --- | -------------- |
| `limit`  | 100     | 100 | Items per page |
| `offset` | 0       | —   | Items to skip  |

```bash
GET /api/pages/?limit=20&offset=40
```

---

## Timestamps

All timestamps use ISO 8601 format in UTC:

```
2025-01-15T10:30:00Z
```

| Field      | Description                    |
| ---------- | ------------------------------ |
| `created`  | When resource was created      |
| `modified` | Last user modification         |
| `updated`  | Last update (including system) |

---

## Resources

| Resource                  | Description                      |
| ------------------------- | -------------------------------- |
| [Ask](../ask/)            | AI-powered Q&A about your pages  |
| [Organizations](../orgs/) | Manage organizations and members |
| [Projects](../projects/)  | Manage projects and sharing      |
| [Pages](../pages/)        | Manage pages and content         |
| [Users](../users/)        | User info and tokens             |
