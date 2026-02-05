# Files

File uploads allow you to store files securely in cloud storage with signed URLs for upload and download.

## Upload Flow

The file upload process follows a three-step flow:

1. **Create Upload** - Get a signed URL for uploading
2. **Upload File** - PUT the file to the signed URL
3. **Finalize Upload** - Confirm the upload and make the file available

---

## List Project Files

List all file uploads for a specific project.

|              |                                 |
| ------------ | ------------------------------- |
| **Endpoint** | `GET /api/files/projects/{id}/` |
| **Auth**     | Bearer token                    |

| Param    | Type   | Description                   |
| -------- | ------ | ----------------------------- |
| `status` | string | Filter by status (optional)   |
| `limit`  | int    | Items per page (default: 100) |
| `offset` | int    | Items to skip (default: 0)    |

**Response (200):**

```json
{
  "items": [
    {
      "external_id": "abc123-...",
      "filename": "document.pdf",
      "content_type": "application/pdf",
      "size_bytes": 12345,
      "status": "available",
      "link": "https://app.example.com/files/...",
      "project": {
        "external_id": "proj-xyz-...",
        "name": "My Project"
      },
      "uploaded_by": {
        "external_id": "user-123-...",
        "username": "john",
        "email": "john@example.com"
      },
      "created": "2025-01-15T10:30:00Z",
      "modified": "2025-01-15T10:35:00Z"
    }
  ],
  "count": 1
}
```

**Access:** Requires read access to the project (org member or project editor/viewer).

---

## List My Files

List all file uploads by the authenticated user.

|              |                        |
| ------------ | ---------------------- |
| **Endpoint** | `GET /api/files/mine/` |
| **Auth**     | Bearer token           |

| Param    | Type   | Description                   |
| -------- | ------ | ----------------------------- |
| `status` | string | Filter by status (optional)   |
| `limit`  | int    | Items per page (default: 100) |
| `offset` | int    | Items to skip (default: 0)    |

**Response (200):** Same schema as [List Project Files](#list-project-files).

**Note:** Returns files from all projects the user has uploaded to.

**Access:** Requires read access to the project (org member or project editor/viewer).

---

## Create Upload

Request a signed URL to upload a file.

|              |                    |
| ------------ | ------------------ |
| **Endpoint** | `POST /api/files/` |
| **Auth**     | Bearer token       |

| Field             | Type   | Required? | Description                                            |
| ----------------- | ------ | --------- | ------------------------------------------------------ |
| `project_id`      | string | Yes       | External ID of the project                             |
| `filename`        | string | Yes       | Original filename (1-255 chars, sanitized server-side) |
| `content_type`    | string | Yes       | MIME type (must be an allowed type, see below)         |
| `size_bytes`      | int    | Yes       | Expected file size in bytes                            |
| `checksum_sha256` | string | No        | SHA-256 checksum for validation                        |
| `metadata`        | object | No        | Arbitrary metadata                                     |

**Response (201):**

```json
{
  "file": {
    "external_id": "abc123-...",
    "project_id": "proj-xyz-...",
    "filename": "document.pdf",
    "content_type": "application/pdf",
    "size_bytes": 12345,
    "status": "pending_url",
    "created": "2025-01-15T10:30:00Z",
    "modified": "2025-01-15T10:30:00Z"
  },
  "upload_url": "https://storage.example.com/signed-url",
  "upload_headers": {
    "Content-Type": "application/pdf"
  },
  "expires_at": "2025-01-15T10:40:00Z",
  "webhook_enabled": true
}
```

**Notes:**

- User must have **edit access** to the project to upload files (org member or project editor with `editor` role)
- Project viewers cannot upload files - they can only view and download existing files
- If `webhook_enabled` is `true`, the file will be automatically finalized after upload
- If `webhook_enabled` is `false`, you must call the finalize endpoint after uploading
- Filenames are sanitized to ASCII alphanumeric characters plus `.`, `-`, and `_`

**Allowed Content Types:**

Only specific MIME types are accepted. Common allowed types include:

- Images: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml`
- Documents: `application/pdf`, Microsoft Office formats, OpenDocument formats
- Text: `text/plain`, `text/markdown`, `text/csv`, `application/json`
- Archives: `application/zip`, `application/gzip`
- Audio/Video: `audio/mpeg`, `video/mp4`, `video/webm`

If an unsupported content type is provided, the API returns `422 Unprocessable Entity`.

**Rate Limits:**

To prevent abuse, file upload creation is rate-limited:

- **Limit**: 60 requests per minute per user
- **Status Code**: `429 Too Many Requests` when exceeded

Plan your uploads accordingly and implement retry logic with exponential backoff.

**File Size Limits:**

- **Maximum file size**: 10 MB (configurable by deployment)
- **Status Code**: `422 Unprocessable Entity` when exceeded

If you need to upload larger files, contact support.

**Upload the file:**

```bash
curl -X PUT "$upload_url" \
  -H "Content-Type: application/pdf" \
  --data-binary @document.pdf
```

---

## Get File

Retrieve detailed file information.

|              |                        |
| ------------ | ---------------------- |
| **Endpoint** | `GET /api/files/{id}/` |
| **Auth**     | Bearer token           |

**Response (200):**

```json
{
  "external_id": "abc123-...",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "available",
  "link": "https://app.example.com/files/...",
  "project": {
    "external_id": "proj-xyz-...",
    "name": "My Project"
  },
  "uploaded_by": {
    "external_id": "user-123-...",
    "username": "john",
    "email": "john@example.com"
  },
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T10:35:00Z"
}
```

**Access:** Requires read access to the file's project (org member or project editor/viewer).

**Status Values:**

| Status        | Description                   |
| ------------- | ----------------------------- |
| `pending_url` | Awaiting file upload          |
| `finalizing`  | Verifying upload              |
| `available`   | Ready for download            |
| `failed`      | Upload or verification failed |

---

## Finalize Upload

Mark the upload as complete after uploading the file.

**Note:** When `webhook_enabled` is `true`, finalization happens automatically. This endpoint is only needed when webhooks are disabled or for error recovery.

|              |                                  |
| ------------ | -------------------------------- |
| **Endpoint** | `POST /api/files/{id}/finalize/` |
| **Auth**     | Bearer token (owner only)        |

| Field  | Type   | Required? | Description               |
| ------ | ------ | --------- | ------------------------- |
| `etag` | string | No        | ETag from upload response |

**Query Parameters:**

| Param         | Type | Description                               |
| ------------- | ---- | ----------------------------------------- |
| `mark_failed` | bool | If true, marks upload as failed (cleanup) |

**Response (200):**

```json
{
  "external_id": "abc123-...",
  "project_id": "proj-xyz-...",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "available",
  "link": "https://app.example.com/files/...",
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T10:35:00Z"
}
```

The `link` field contains the permanent download URL for the finalized file.

**Errors:**

- `400` - File not found in storage or size mismatch

---

## Get Download URL

Get a permanent download URL for the file.

|              |                                 |
| ------------ | ------------------------------- |
| **Endpoint** | `GET /api/files/{id}/download/` |
| **Auth**     | Bearer token                    |

**Response (200):**

```json
{
  "download_url": "https://app.example.com/files/{project_id}/{file_id}/{access_token}/",
  "provider": "hyper",
  "expires_at": null
}
```

The returned URL:

- **Never expires** - can be shared and bookmarked
- **No authentication required** - the access token in the URL authorizes the download
- **Redirects to storage** - when accessed, redirects to a short-lived signed storage URL

**Errors:**

- `400` - File not available (not yet finalized or failed)
- `403` - User does not have access to the file's project

---

## Public Download

Download a file using its permanent URL with access token.

|              |                                                     |
| ------------ | --------------------------------------------------- |
| **Endpoint** | `GET /files/{project_id}/{file_id}/{access_token}/` |
| **Auth**     | None (access token in URL provides authorization)   |

**Response:**

- `302` - Redirects to a short-lived signed storage URL (valid for 5 minutes)
- `404` - File not found, deleted, or invalid token

**Notes:**

- This is a public endpoint - no authentication header required
- The access token is generated when the file is finalized
- Each file has a unique access token that can be regenerated

---

## Regenerate Access Token

Regenerate the access token, invalidating all existing download links.

|              |                                          |
| ------------ | ---------------------------------------- |
| **Endpoint** | `POST /api/files/{id}/regenerate-token/` |
| **Auth**     | Bearer token (uploader only)             |

**Response (200):**

```json
{
  "download_url": "https://app.example.com/files/{project_id}/{file_id}/{new_access_token}/",
  "provider": "hyper",
  "expires_at": null
}
```

**Notes:**

- Only the user who uploaded the file can regenerate its token
- All previously shared URLs will stop working immediately
- Use this to revoke access if a link was shared incorrectly

**Errors:**

- `403` - Only the uploader can regenerate the token
- `404` - File not found

---

## Delete File

Soft-delete a file upload.

|              |                           |
| ------------ | ------------------------- |
| **Endpoint** | `DELETE /api/files/{id}/` |
| **Auth**     | Bearer token (owner only) |

**Response (204):** No content

**Notes:**

- Files are soft-deleted and may be recoverable
- Storage is cleaned up by background processes

---

## Get File References

Get a list of pages that link to this file. Useful for warning users before deleting a file that is referenced in pages.

|              |                                   |
| ------------ | --------------------------------- |
| **Endpoint** | `GET /api/files/{id}/references/` |
| **Auth**     | Bearer token                      |

**Response (200):**

```json
{
  "references": [
    {
      "page_external_id": "page-123-...",
      "page_title": "My Notes",
      "link_text": "screenshot"
    }
  ],
  "count": 1
}
```

**Notes:**

- Returns pages that contain markdown links to this file
- Excludes deleted pages and pages in deleted projects
- Pages without a title show "Untitled"
- The `link_text` is the text displayed in the markdown link (e.g., `[link_text](/files/...)`)

**Access:** Requires read access to the file's project (org member or project editor/viewer).

**Errors:**

- `403` - User does not have access to the file's project
- `404` - File not found or deleted

---

## Complete Example

```python
import requests

# 1. Create upload (requires project_id)
response = requests.post(
    "https://api.example.com/api/files/",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "project_id": "proj-xyz-...",  # Required: project external ID
        "filename": "report.pdf",
        "content_type": "application/pdf",
        "size_bytes": 1048576
    }
)
data = response.json()
upload_url = data["upload_url"]
file_id = data["file"]["external_id"]

# 2. Upload file to signed URL
with open("report.pdf", "rb") as f:
    requests.put(
        upload_url,
        data=f,
        headers=data["upload_headers"]
    )

# 3. Finalize
requests.post(
    f"https://api.example.com/api/files/{file_id}/finalize/",
    headers={"Authorization": f"Bearer {token}"}
)

# 4. Download
response = requests.get(
    f"https://api.example.com/api/files/{file_id}/download/",
    headers={"Authorization": f"Bearer {token}"}
)
download_url = response.json()["download_url"]
```
