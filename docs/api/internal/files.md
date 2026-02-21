# Files API

## Table of Contents

- [List project files](#list-project-files)
- [List my files](#list-my-files)
- [Create a file upload](#create-a-file-upload)
- [Get a file upload](#get-a-file-upload)
- [Finalize a file upload](#finalize-a-file-upload)
- [Get a download URL](#get-a-download-url)
- [Delete a file upload](#delete-a-file-upload)
- [Get file references](#get-file-references)
- [Webhooks](#webhooks)
  - [R2 Event Webhook](#r2-event-webhook)

## List project files

List all file uploads for a specific project with pagination.

### URL

`/api/files/projects/{project_id}/`

### HTTP Method

`GET`

### Path Params

- `project_id` (String, required): The external ID of the project

### Query Params

- `status` (String, optional): Filter by file status (pending_url, finalizing, available, failed)
- `limit` (Integer, optional): Number of items per page (default: 100)
- `offset` (Integer, optional): Number of items to skip (default: 0)

### Data Params

None

### Authorization

Requires authentication. User must have **read access** to the project via `user_can_access_project()`:

- Org admin (Tier 0)
- Org member when `org_members_can_access=True` (Tier 1)
- Project editor with any role (Tier 2)

**Note:** Page-only users (Tier 3) cannot list project files because files are project-scoped.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "items": [
    {
      "external_id": "abc123-...",
      "filename": "document.pdf",
      "content_type": "application/pdf",
      "size_bytes": 12345,
      "status": "available",
      "link": "https://app.example.com/files/proj-id/file-id/token/",
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

**Notes:**

- Files are sorted by creation date, newest first
- Soft-deleted files are excluded from the list
- The `link` field contains a permanent download URL (if available)

**Error Responses:**

- Status Code: 403 - User does not have access to the project
- Status Code: 404 - Project not found

---

## List my files

List all file uploads by the authenticated user with pagination.

### URL

`/api/files/mine/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

- `status` (String, optional): Filter by file status (pending_url, finalizing, available, failed)
- `limit` (Integer, optional): Number of items per page (default: 100)
- `offset` (Integer, optional): Number of items to skip (default: 0)

### Data Params

None

### Authorization

Requires authentication.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema: Same as [List project files](#list-project-files)

**Notes:**

- Returns only files uploaded by the authenticated user
- Includes files from all projects the user has uploaded to
- Files are sorted by creation date, newest first
- Soft-deleted files are excluded

---

## Create a file upload

Create a new file upload and receive a signed URL for uploading the file directly to storage.

### URL

`/api/files/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `project_id` (String, required): The external ID of the project this file belongs to.
- `filename` (String, required): The original filename. Must be 1-255 characters. The server sanitizes filenames to ASCII alphanumeric characters plus `.`, `-`, and `_`.
- `content_type` (String, required): The MIME type of the file (e.g., "image/png", "application/pdf"). Must be an allowed content type (see below).
- `size_bytes` (Integer, required): Expected file size in bytes. Must be greater than 0.
- `checksum_sha256` (String, optional): SHA-256 checksum for verification.
- `metadata` (Object, optional): Arbitrary metadata to store with the upload.

### Authorization

Requires authentication. User must have **edit access** to the project via `user_can_edit_in_project()`:

- Org admin (Tier 0)
- Org member when `org_members_can_access=True` (Tier 1)
- Project editor with `editor` role (Tier 2)

**Important:** Project viewers (role=viewer) cannot upload files. They can only view and download existing files.

**Note:** Page-only users (Tier 3) cannot upload files because files are project-scoped.

See [Overview](./overview.md) for details on session-based authentication.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "file": {
    "external_id": "abc123-def456-...",
    "project_id": "proj-xyz-789-...",
    "filename": "document.pdf",
    "content_type": "application/pdf",
    "size_bytes": 12345,
    "status": "pending_url",
    "link": "https://app.example.com/files/proj-id/file-id/token/",
    "created": "2025-01-15T10:30:00Z",
    "modified": "2025-01-15T10:30:00Z"
  },
  "upload_url": "https://storage.example.com/signed-upload-url",
  "upload_headers": {
    "Content-Type": "application/pdf",
    "x-amz-content-sha256": "UNSIGNED-PAYLOAD"
  },
  "expires_at": "2025-01-15T10:40:00Z",
  "webhook_enabled": true
}
```

**Notes:**

- Use the `upload_url` to PUT the file directly to storage
- Include all `upload_headers` in your upload request
- The URL expires after a configurable period (default 10 minutes)
- If `webhook_enabled` is `true`, the file will be automatically finalized via R2 event notification webhook after upload completes
- If `webhook_enabled` is `false`, call the finalize endpoint after uploading
- Files belong to exactly one project; access is controlled via project membership
- The `link` field contains the permanent download URL. This URL is available immediately even before finalization, but the download will only work once the file upload is finalized (status becomes "available")

**Example Request:**

```json
{
  "project_id": "proj-xyz-789-...",
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "size_bytes": 1048576,
  "metadata": {
    "source": "web-upload"
  }
}
```

**Error Responses:**

| Status Code | Description                                                   |
| ----------- | ------------------------------------------------------------- |
| 403         | User does not have access to the specified project            |
| 404         | Project not found                                             |
| 413         | File size exceeds configured maximum                          |
| 422         | Validation error (invalid filename, size, content type, etc.) |
| 429         | Rate limit exceeded                                           |

### Allowed Content Types

The API validates that the `content_type` is in the configured allowlist. Default allowed types include:

- **Images**: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/svg+xml`, `image/bmp`, `image/tiff`, `image/x-icon`, `image/heic`, `image/heif`, `image/avif`
- **Documents**: `application/pdf`, `application/msword`, `application/vnd.openxmlformats-officedocument.*` (Word, Excel, PowerPoint), `application/vnd.oasis.opendocument.*` (ODF)
- **Text**: `text/plain`, `text/markdown`, `text/csv`, `text/html`, `text/css`, `text/javascript`, `application/json`, `application/xml`
- **Archives**: `application/zip`, `application/gzip`, `application/x-tar`, `application/x-7z-compressed`, `application/x-rar-compressed`
- **Audio**: `audio/mpeg`, `audio/wav`, `audio/ogg`, `audio/webm`, `audio/flac`, `audio/aac`, `audio/mp4`
- **Video**: `video/mp4`, `video/webm`, `video/ogg`, `video/quicktime`, `video/x-msvideo`, `video/x-matroska`
- **Fonts**: `font/ttf`, `font/otf`, `font/woff`, `font/woff2`

If an unsupported content type is provided, the API returns a 422 error with a message indicating the content type is not allowed. The allowlist can be customized via the `WS_FILEHUB_ALLOWED_CONTENT_TYPES` setting.

### Rate Limiting

The file upload creation endpoint is rate-limited to prevent abuse:

| Limit Type | Default            | Configuration                                 |
| ---------- | ------------------ | --------------------------------------------- |
| Per User   | 60 requests/minute | `WS_FILEHUB_UPLOAD_RATE_LIMIT_REQUESTS`       |
| Window     | 60 seconds         | `WS_FILEHUB_UPLOAD_RATE_LIMIT_WINDOW_SECONDS` |

When rate limited, the API returns:

- **Status Code**: `429 Too Many Requests`
- **Response**: `{"error": "error", "message": "Request was throttled.", "detail": "Request was throttled."}`

### File Size Limits

| Limit             | Default                | Configuration                    |
| ----------------- | ---------------------- | -------------------------------- |
| Maximum file size | 10 MB (10485760 bytes) | `WS_FILEHUB_MAX_FILE_SIZE_BYTES` |

When file size exceeds the limit:

- **Status Code**: `422 Unprocessable Entity`
- **Response**: Validation error with message "File size exceeds maximum allowed size of X bytes"

---

## Get a file upload

Retrieve details of a specific file upload.

### URL

`/api/files/{external_id}/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the file upload

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have **read access** to the file's project via `user_can_access_project()`:

- Org admin (Tier 0)
- Org member when `org_members_can_access=True` (Tier 1)
- Project editor with any role (Tier 2)

**Note:** Page-only users (Tier 3) cannot view file details because files are project-scoped.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123-def456-...",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "available",
  "link": "https://app.example.com/files/proj-id/file-id/token/",
  "project": {
    "external_id": "proj-xyz-789-...",
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

**Notes:**

- Status values: `pending_url`, `finalizing`, `available`, `failed`
- The `link` field contains the permanent download URL
- Includes nested `project` and `uploaded_by` info
- Both project editors and viewers can view file details

**Error Responses:**

- Status Code: 403 - User does not have access to the file's project
- Status Code: 404 - File not found

---

## Finalize a file upload

Finalize a file upload after the file has been uploaded to storage. This verifies the file exists and marks it as available for download.

**Note:** When `webhook_enabled` is `true` in the create response, finalization happens automatically via R2 event notifications. This endpoint is only needed when webhooks are disabled or for error recovery.

### URL

`/api/files/{external_id}/finalize/`

### HTTP Method

`POST`

### Path Params

- `external_id` (String, required): The external ID of the file upload

### Query Params

- `mark_failed` (Boolean, optional): If `true`, marks the upload as failed instead of finalizing. Used for error recovery when upload to storage fails.

### Data Params

- `etag` (String, optional): ETag from the upload response for verification

### Authorization

Requires authentication. Only the original uploader can finalize or mark an upload as failed. This prevents other project members from interfering with in-progress uploads.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123-def456-...",
  "project_id": "proj-xyz-789-...",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "status": "available",
  "link": "https://app.example.com/files/proj-id/file-id/token/",
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T10:35:00Z"
}
```

**Notes:**

- The `link` field contains the permanent download URL for the finalized file
- This endpoint is idempotent - safe to call multiple times
- Uses database locking to prevent race conditions with concurrent finalization attempts
- Verifies the file size matches the expected size from upload creation
- If replication is enabled, triggers background replication to other storage providers
- When `mark_failed=true`:
  - Marks the upload as `failed` (unless already `available`)
  - Also marks any pending blobs as failed
  - Does not contact storage - useful for cleanup when upload failed client-side
  - Cannot mark `available` files as failed

**Error Responses:**

- Status Code: 400 - Finalization failed (e.g., file not found in storage, size mismatch)
- Status Code: 403 - User is not the original uploader
- Status Code: 404 - File upload not found

---

## Get a download URL

Generate a signed download URL for a file.

### URL

`/api/files/{external_id}/download/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the file upload

### Query Params

- `filename` (String, optional): Override the filename in the Content-Disposition header
- `provider` (String, optional): Preferred storage provider ("r2" or "local")

### Data Params

None

### Authorization

Requires authentication. User must have **read access** to the file's project via `user_can_access_project()`:

- Org admin (Tier 0)
- Org member when `org_members_can_access=True` (Tier 1)
- Project editor with any role (Tier 2)

**Note:** Both project editors and viewers can download files. Page-only users (Tier 3) cannot download files because files are project-scoped.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "download_url": "https://storage.example.com/signed-download-url",
  "provider": "r2",
  "expires_at": "2025-01-15T10:40:00Z"
}
```

**Notes:**

- The URL expires after a configurable period (default 10 minutes)
- The file must be in "available" status
- If multiple storage providers have the file, R2 is preferred over local

**Error Responses:**

- Status Code: 400 - File not available for download (e.g., still pending, failed)
- Status Code: 403 - User does not have access to the file's project
- Status Code: 404 - File not found

**Example Usage:**

```bash
# Get download URL with custom filename
GET /api/files/abc123/download/?filename=my-report.pdf

# Get download URL from specific provider
GET /api/files/abc123/download/?provider=local
```

---

## Delete a file upload

Soft-delete a file upload. The file is marked as deleted but not immediately removed from storage.

### URL

`/api/files/{external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the file upload

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be the uploader of the file AND have access to the file's project.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- This is a soft delete - the file and its blobs are marked as deleted
- Deleted files will not appear in listings and cannot be downloaded
- Storage cleanup is handled by a separate background process
- Only the original uploader can delete the file, even if others have project access

**Error Responses:**

- Status Code: 403 - User is not the uploader or does not have project access
- Status Code: 404 - File not found

---

## Get file references

Get a list of pages that link to this file. This is useful for warning users before deleting a file that is referenced in pages.

### URL

`/api/files/{external_id}/references/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the file upload

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have **read access** to the file's project via `user_can_access_project()`:

- Org admin (Tier 0)
- Org member when `org_members_can_access=True` (Tier 1)
- Project editor with any role (Tier 2)

**Note:** Page-only users (Tier 3) cannot view file references because files are project-scoped.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "references": [
    {
      "page_external_id": "page-123-abc-...",
      "page_title": "My Notes",
      "link_text": "screenshot"
    }
  ],
  "count": 1
}
```

**Notes:**

- Returns pages that contain markdown links to this file (e.g., `[screenshot](/files/proj/file/token/)`)
- Excludes deleted pages and pages in deleted projects
- Pages without a title show "Untitled" in the response
- The `link_text` field contains the display text from the markdown link
- File links are tracked automatically when pages are saved via real-time collaboration
- Uses the `FileLink` model which mirrors the `PageLink` pattern for page-to-page links

**Error Responses:**

- Status Code: 403 - User does not have access to the file's project
- Status Code: 404 - File not found or deleted

---

## Webhooks

### R2 Event Webhook

This endpoint receives R2 bucket event notifications from a Cloudflare Worker. It automatically finalizes uploads when files are uploaded to storage and marks files as unavailable when storage objects are deleted.

**This is an internal endpoint used by the R2 webhook infrastructure, not for direct client use.**

### URL

`/api/files/webhooks/r2-events/`

### HTTP Method

`POST`

### Authentication

This endpoint does not use standard authentication. Instead, it uses HMAC-SHA256 signature verification:

- The Cloudflare Worker signs the request body with a shared secret
- The signature is included in the `X-Webhook-Signature` header
- The backend verifies the signature before processing

### Request Headers

- `Content-Type: application/json`
- `X-Webhook-Signature`: HMAC-SHA256 signature of the request body
- `X-Request-Id` (optional): Request ID for tracing

### Data Params

```json
{
  "account": "cloudflare-account-id",
  "bucket": "bucket-name",
  "eventTime": "2025-01-15T10:30:00Z",
  "eventType": "PutObject",
  "object": {
    "key": "users/{user_id}/files/{file_id}/filename.pdf",
    "size": 12345,
    "eTag": "\"abc123def456\""
  }
}
```

**Supported Event Types:**

| Event Type                | Action                                       |
| ------------------------- | -------------------------------------------- |
| `PutObject`               | Finalize upload                              |
| `CompleteMultipartUpload` | Finalize upload                              |
| `CopyObject`              | Finalize upload                              |
| `DeleteObject`            | Mark blob as failed, potentially fail upload |
| `LifecycleDeletion`       | Mark blob as failed, potentially fail upload |

### Response

- Status Code: 200
- Schema:

```json
{
  "status": "finalized",
  "message": "File upload successfully finalized",
  "file_id": "abc123-def456-..."
}
```

**Status Values:**

| Status              | Description                                   |
| ------------------- | --------------------------------------------- |
| `finalized`         | Upload successfully finalized                 |
| `already_processed` | Upload was already finalized (idempotent)     |
| `processed`         | Delete event processed, file still has blobs  |
| `file_unavailable`  | Delete event processed, file marked as failed |
| `ignored`           | Event type not processed or file not found    |
| `disabled`          | Webhook processing is disabled                |
| `error`             | Processing failed                             |

**Error Responses:**

- Status Code: 400 - Invalid event or processing failed
- Status Code: 401 - Invalid or missing signature
- Status Code: 429 - Rate limit exceeded

**Note:** For security reasons, the webhook returns 200 with `status: "ignored"` when a file upload is not found, rather than 404. This prevents attackers from probing for valid file IDs.

### Rate Limiting

- Burst: 60 requests per minute per IP
- Daily: 10,000 requests per day per IP

### Configuration

The webhook is controlled by these settings:

- `WS_FILEHUB_R2_WEBHOOK_ENABLED`: Enable/disable webhook processing
- `WS_FILEHUB_R2_WEBHOOK_SECRET`: Shared secret for signature verification

See the [R2 Webhook Worker Setup Guide](../../../docs/cloudflare/r2-webhook-worker-setup.md) for deployment instructions.
