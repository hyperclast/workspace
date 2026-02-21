# Imports API

## Table of Contents

- [List import jobs](#list-import-jobs)
- [Start Notion import](#start-notion-import)
- [Get import job](#get-import-job)
- [List imported pages](#list-imported-pages)
- [Delete import job](#delete-import-job)

## List import jobs

List all import jobs for the authenticated user with pagination.

### URL

`/api/imports/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

- `status` (String, optional): Filter by job status (`pending`, `processing`, `completed`, `failed`)
- `provider` (String, optional): Filter by import provider (`notion`)
- `limit` (Integer, optional): Number of items per page (default: 100)
- `offset` (Integer, optional): Number of items to skip (default: 0)

### Data Params

None

### Authorization

Requires authentication. Returns only jobs belonging to the authenticated user.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "items": [
    {
      "external_id": "550e8400-e29b-41d4-a716-446655440000",
      "provider": "notion",
      "status": "completed",
      "total_pages": 25,
      "pages_imported_count": 23,
      "pages_skipped_count": 2,
      "pages_failed_count": 0,
      "error_message": null,
      "project": {
        "external_id": "proj-xyz-...",
        "name": "My Project"
      },
      "created": "2025-01-15T10:30:00Z",
      "modified": "2025-01-15T10:35:00Z"
    }
  ],
  "count": 1
}
```

**Notes:**

- Jobs are sorted by creation date, newest first
- `pages_skipped_count` tracks duplicates that were not re-imported

---

## Start Notion import

Upload a Notion export zip file and start async import processing.

### URL

`/api/imports/notion/`

### HTTP Method

`POST`

### Content-Type

`multipart/form-data`

### Path Params

None

### Query Params

None

### Data Params

- `project_id` (String, required): External ID of the target project
- `file` (File, required): Notion export zip file

### Authorization

Requires authentication. User must have **editor (write) permission** on the target project. This includes:

- Org admins
- Org members (when `org_members_can_access=True`)
- Project editors with `editor` role

**Note:** Project editors with `viewer` role cannot start imports, even though they have read access to the project. This is because imports create new pages, which is a write operation.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "job": {
    "external_id": "550e8400-e29b-41d4-a716-446655440000",
    "provider": "notion",
    "status": "pending",
    "total_pages": 0,
    "pages_imported_count": 0,
    "pages_skipped_count": 0,
    "pages_failed_count": 0,
    "error_message": null,
    "project": {
      "external_id": "proj-xyz-...",
      "name": "My Project"
    },
    "created": "2025-01-15T10:30:00Z",
    "modified": "2025-01-15T10:30:00Z"
  },
  "message": "Import job started. Processing will continue in the background."
}
```

**Notes:**

- The job is processed asynchronously via the `imports` RQ queue
- Poll `GET /api/imports/{id}/` to check job status
- Duplicate pages (matching `source_hash` in the same project) are automatically skipped

**Notion Export Format:**

The endpoint accepts Notion's "Markdown & CSV" export format:

- Files must have `.zip` extension with `application/zip` content type
- Nested zips (`ExportBlock-*-Part-*.zip`) are automatically extracted
- Page filenames follow the pattern: `{Title} {hash}.md`
- Child folders use title-only names (not `{Title} {hash}/`)

**Error Responses:**

| Status Code | Error                  | Description                                                            |
| ----------- | ---------------------- | ---------------------------------------------------------------------- |
| 400         | `invalid_content_type` | File is not a zip                                                      |
| 403         | `forbidden`            | User does not have editor permission on the project (includes viewers) |
| 404         | -                      | Project not found                                                      |
| 413         | `file_too_large`       | File exceeds maximum size (default 100MB)                              |
| 429         | `temporarily_blocked`  | User is temporarily banned due to abuse                                |
| 429         | -                      | Rate limit exceeded                                                    |

**Note on 429 Responses:**

If a user triggers too many security violations (e.g., uploading zip bombs), they may be temporarily banned from importing. The response will include:

```json
{
  "error": "temporarily_blocked",
  "message": "Import temporarily unavailable. Please try again later.",
  "detail": null
}
```

Bans are permanent until lifted by an administrator via Django admin.

### Rate Limiting

| Limit Type | Default          | Configuration                          |
| ---------- | ---------------- | -------------------------------------- |
| Per User   | 10 requests/hour | `WS_IMPORTS_RATE_LIMIT_REQUESTS`       |
| Window     | 3600 seconds     | `WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS` |

### File Size Limits

| Limit             | Default                  | Configuration                    |
| ----------------- | ------------------------ | -------------------------------- |
| Maximum file size | 100 MB (104857600 bytes) | `WS_IMPORTS_MAX_FILE_SIZE_BYTES` |

### Archive Security Limits

Uploaded archives are validated before extraction to prevent zip bombs and other attacks:

| Limit                 | Default   | Configuration                            |
| --------------------- | --------- | ---------------------------------------- |
| Max uncompressed size | 5 GB      | `WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES` |
| Max compression ratio | 30x       | `WS_IMPORTS_MAX_COMPRESSION_RATIO`       |
| Max file count        | 100,000   | `WS_IMPORTS_MAX_FILE_COUNT`              |
| Max single file size  | 1 GB      | `WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES`  |
| Max path depth        | 30        | `WS_IMPORTS_MAX_PATH_DEPTH`              |
| Max nested zip depth  | 2         | `WS_IMPORTS_MAX_NESTED_ZIP_DEPTH`        |
| Extraction timeout    | 5 minutes | `WS_IMPORTS_EXTRACTION_TIMEOUT_SECONDS`  |

If any limit is exceeded, the import fails and an abuse record is created. Repeated violations may result in a permanent ban.

---

## Get import job

Get detailed information about a specific import job.

### URL

`/api/imports/{external_id}/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the import job

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. Only the job owner can view it.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "550e8400-e29b-41d4-a716-446655440000",
  "provider": "notion",
  "status": "completed",
  "total_pages": 25,
  "pages_imported_count": 23,
  "pages_skipped_count": 2,
  "pages_failed_count": 0,
  "error_message": null,
  "project": {
    "external_id": "proj-xyz-...",
    "name": "My Project"
  },
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T10:35:00Z"
}
```

**Status Values:**

| Status       | Description                                     |
| ------------ | ----------------------------------------------- |
| `pending`    | Job created, waiting for worker to pick it up   |
| `processing` | Worker is actively processing the import        |
| `completed`  | Import finished (may have skipped/failed pages) |
| `failed`     | Import failed (see `error_message`)             |

**Notes:**

- `total_pages` is set when processing begins (after parsing the zip)
- `pages_skipped_count` tracks pages that already existed (by `source_hash`)
- Poll this endpoint to track import progress

**Error Responses:**

- Status Code: 403 - User is not the job owner
- Status Code: 404 - Import job not found

---

## List imported pages

List all pages created by a specific import job with pagination.

### URL

`/api/imports/{external_id}/pages/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the import job

### Query Params

- `limit` (Integer, optional): Number of items per page (default: 100)
- `offset` (Integer, optional): Number of items to skip (default: 0)

### Data Params

None

### Authorization

Requires authentication. Only the job owner can view it.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "items": [
    {
      "page": {
        "external_id": "page-abc-123-...",
        "title": "My Notes"
      },
      "original_path": "Parent Page abc123/My Notes def456.md",
      "source_hash": "def456abc789012345"
    }
  ],
  "count": 23
}
```

**Notes:**

- `original_path` preserves the Notion folder structure for reference
- `source_hash` is the identifier used for deduplication
- Only includes successfully imported pages (not skipped duplicates)

**Error Responses:**

- Status Code: 403 - User is not the job owner
- Status Code: 404 - Import job not found

---

## Delete import job

Delete an import job record. Note: This only deletes the job metadata, not the imported pages.

### URL

`/api/imports/{external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the import job

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. Only the job owner can delete it.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- Imported pages remain in the project after job deletion
- The `ImportArchive` (R2 backup) is also deleted
- `ImportedPage` records are cascade-deleted

**Error Responses:**

- Status Code: 403 - User is not the job owner
- Status Code: 404 - Import job not found
