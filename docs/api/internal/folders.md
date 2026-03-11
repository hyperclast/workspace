# Folders API (Internal)

Folders provide hierarchical organization within projects using an adjacency list pattern (`parent_id` FK).

## Endpoints

All folder endpoints are nested under the project URL.

### Get Folder

```
GET /api/v1/projects/{project_id}/folders/{folder_id}/
```

**Permission:** `user_can_access_project()`

**Response (200):**

```json
{ "external_id": "fld_abc", "parent_id": null, "name": "Design" }
```

### Create Folder

```
POST /api/v1/projects/{project_id}/folders/
```

**Permission:** `user_can_edit_in_project()`
**Rate limited:** 60 req/60s per user (configurable)

**Request:**

```json
{ "name": "Design", "parent_id": null }
```

`parent_id` is the `external_id` of the parent folder, or `null` for top-level.

**Response (201):**

```json
{ "external_id": "fld_abc", "parent_id": null, "name": "Design" }
```

**Validation:**

- Name: 1–255 chars, no `/`, `\`, `\0`, or control characters
- Max 500 folders per project
- Max 10 levels of nesting depth
- Duplicate names under the same parent are rejected (409)

### Update Folder (Rename/Move)

```
PATCH /api/v1/projects/{project_id}/folders/{folder_id}/
```

**Permission:** `user_can_edit_in_project()`
**Rate limited:** 60 req/60s per user

**Request:**

```json
{ "name": "Visual", "parent_id": "other_folder_ext_id" }
```

Both fields are optional. Include `name` to rename, `parent_id` to move.

**Validation:**

- Same name validation as create
- Cycle detection: cannot move a folder into its own descendant
- Depth check: resulting tree cannot exceed 10 levels
- Name collision: rejects if target parent already has a folder with the same name (409)

### Delete Folder

```
DELETE /api/v1/projects/{project_id}/folders/{folder_id}/
```

**Permission:** `user_can_edit_in_project()`
**Rate limited:** 60 req/60s per user

Deletes an empty folder. Returns 409 if the folder has pages or subfolders.

### Bulk Move Pages

```
POST /api/v1/projects/{project_id}/folders/move-pages/
```

**Permission:** `user_can_edit_in_project()`
**Rate limited:** 60 req/60s per user

**Request:**

```json
{ "page_ids": ["pg_abc", "pg_def"], "folder_id": "fld_abc" }
```

`folder_id` can be `null` to move pages to project root.

## Error Codes

| Status | Code                   | Condition                        |
| ------ | ---------------------- | -------------------------------- |
| 400    | `name_required`        | Empty or whitespace-only name    |
| 400    | `name_too_long`        | Name exceeds 255 characters      |
| 400    | `invalid_name`         | Forbidden characters in name     |
| 400    | `cycle_detected`       | Move would create a cycle        |
| 400    | `depth_limit_exceeded` | Tree would exceed 10 levels      |
| 400    | `folder_limit_reached` | Project has 500+ folders         |
| 404    |                        | Folder or parent not found       |
| 409    | `duplicate_name`       | Name collision under same parent |
| 409    | `folder_not_empty`     | Delete of non-empty folder       |
| 429    |                        | Rate limit exceeded              |

## Real-Time Sync

All write operations broadcast a `folders_updated` event via the project WebSocket channel group. Clients refetch the folder tree on receipt.

## Project Detail Response

`GET /api/v1/projects/{id}/?details=full` includes folders:

```json
{
  "folders": [
    { "external_id": "fld_1", "parent_id": null, "name": "Design" },
    { "external_id": "fld_2", "parent_id": "fld_1", "name": "Wireframes" }
  ],
  "pages": [{ "external_id": "pg_a", "folder_id": "fld_2", "title": "Mobile Nav" }]
}
```
