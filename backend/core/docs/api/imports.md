# Imports

Import pages from external sources like Notion into your Hyperclast projects.

## Overview

The import system allows you to migrate content from external note-taking apps:

1. **Export** your data from the source app (e.g., Notion → Markdown & CSV)
2. **Upload** the export zip file to Hyperclast
3. **Wait** for async processing to complete
4. **Access** your imported pages in the target project

Currently supported: **Notion** (Markdown & CSV export format)

---

## List Import Jobs

List all your import jobs.

|              |                     |
| ------------ | ------------------- |
| **Endpoint** | `GET /api/imports/` |
| **Auth**     | Bearer token        |

| Param      | Type   | Description                                            |
| ---------- | ------ | ------------------------------------------------------ |
| `status`   | string | Filter: `pending`, `processing`, `completed`, `failed` |
| `provider` | string | Filter: `notion`                                       |
| `limit`    | int    | Items per page (default: 100)                          |
| `offset`   | int    | Items to skip (default: 0)                             |

**Response (200):**

```json
{
  "items": [
    {
      "external_id": "550e8400-e29b-41d4-...",
      "provider": "notion",
      "status": "completed",
      "total_pages": 25,
      "pages_imported_count": 23,
      "pages_skipped_count": 2,
      "pages_failed_count": 0,
      "project": {
        "external_id": "proj-xyz-...",
        "name": "My Project"
      },
      "created": "2025-01-15T10:30:00Z"
    }
  ],
  "count": 1
}
```

---

## Start Notion Import

Upload a Notion export and start import processing.

|              |                             |
| ------------ | --------------------------- |
| **Endpoint** | `POST /api/imports/notion/` |
| **Auth**     | Bearer token                |
| **Content**  | `multipart/form-data`       |

| Field        | Type   | Required | Description                |
| ------------ | ------ | -------- | -------------------------- |
| `project_id` | string | Yes      | Target project external ID |
| `file`       | file   | Yes      | Notion export zip file     |

**Permission Required:** You must have **editor** permission on the target project. Viewers cannot start imports.

**Response (201):**

```json
{
  "job": {
    "external_id": "550e8400-e29b-41d4-...",
    "provider": "notion",
    "status": "pending",
    "total_pages": 0,
    "pages_imported_count": 0,
    "project": { ... },
    "created": "2025-01-15T10:30:00Z"
  },
  "message": "Import job started. Processing will continue in the background."
}
```

**How to Export from Notion:**

1. Open Notion and go to Settings → Export
2. Choose "Markdown & CSV" format
3. Select pages/workspace to export
4. Download the zip file
5. Upload to this endpoint

**Notes:**

- Processing is async - poll the job status endpoint
- Duplicate pages are automatically skipped
- Internal Notion links are remapped to Hyperclast links
- Maximum file size: 100 MB
- Archives are validated for security (zip bomb protection)

**Errors:**

| Code | Description                                             |
| ---- | ------------------------------------------------------- |
| 400  | Invalid file type (not a zip)                           |
| 403  | No editor permission on project (viewers cannot import) |
| 413  | File too large                                          |
| 429  | Rate limited or temporarily banned                      |

**Security Limits:**

Uploads are validated to prevent malicious archives:

| Limit                 | Default |
| --------------------- | ------- |
| Max uncompressed size | 5 GB    |
| Max compression ratio | 30x     |
| Max file count        | 100,000 |
| Extraction timeout    | 5 min   |

Repeated security violations may result in a temporary import ban.

---

## Get Import Job

Get the status of an import job.

|              |                          |
| ------------ | ------------------------ |
| **Endpoint** | `GET /api/imports/{id}/` |
| **Auth**     | Bearer token             |

**Response (200):**

```json
{
  "external_id": "550e8400-e29b-41d4-...",
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

| Status       | Description                  |
| ------------ | ---------------------------- |
| `pending`    | Waiting to be processed      |
| `processing` | Currently importing pages    |
| `completed`  | Finished successfully        |
| `failed`     | Failed (see `error_message`) |

---

## List Imported Pages

List pages created by an import job.

|              |                                |
| ------------ | ------------------------------ |
| **Endpoint** | `GET /api/imports/{id}/pages/` |
| **Auth**     | Bearer token                   |

| Param    | Type | Description                   |
| -------- | ---- | ----------------------------- |
| `limit`  | int  | Items per page (default: 100) |
| `offset` | int  | Items to skip (default: 0)    |

**Response (200):**

```json
{
  "items": [
    {
      "page": {
        "external_id": "page-abc-...",
        "title": "My Notes"
      },
      "original_path": "Parent/My Notes abc123.md",
      "source_hash": "abc123def456789012"
    }
  ],
  "count": 23
}
```

---

## Delete Import Job

Delete an import job record.

|              |                             |
| ------------ | --------------------------- |
| **Endpoint** | `DELETE /api/imports/{id}/` |
| **Auth**     | Bearer token                |

**Response:** 204 No Content

**Note:** This only deletes the job record. Imported pages remain in the project.
