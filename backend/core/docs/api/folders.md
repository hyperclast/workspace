# Folders API

Folders organize pages within projects into a hierarchical tree structure.

## Endpoints

### Get Folder

```
GET /api/v1/projects/{project_id}/folders/{folder_id}/
```

Returns a single folder's metadata.

**Response:**

```json
{ "external_id": "fld_abc", "parent_id": null, "name": "Design" }
```

### Create Folder

```
POST /api/v1/projects/{project_id}/folders/
```

**Request:**

```json
{ "name": "Design", "parent_id": null }
```

- `name` — Folder name (1–255 characters)
- `parent_id` — Parent folder `external_id`, or `null` for top-level

**Limits:** Max 500 folders per project, max 10 nesting levels.

### Update Folder

```
PATCH /api/v1/projects/{project_id}/folders/{folder_id}/
```

**Request:**

```json
{ "name": "Visual Design", "parent_id": "fld_xyz" }
```

Both fields are optional. Include `name` to rename, `parent_id` to move.

### Delete Folder

```
DELETE /api/v1/projects/{project_id}/folders/{folder_id}/
```

Folder must be empty (no pages or subfolders). Returns `409` if not.

### Bulk Move Pages

```
POST /api/v1/projects/{project_id}/folders/move-pages/
```

**Request:**

```json
{ "page_ids": ["pg_abc", "pg_def"], "folder_id": "fld_abc" }
```

Set `folder_id` to `null` to move pages to project root.

## Folder Tree

The full folder tree is included in the project detail response:

```
GET /api/v1/projects/{project_id}/?details=full
```

Returns flat arrays of folders and pages. Build the tree client-side using `parent_id` and `folder_id` references.

## Creating Pages in Folders

Pass `folder_id` when creating a page:

```
POST /api/v1/pages/
{ "project_id": "...", "title": "New Page", "folder_id": "fld_abc" }
```

## Moving Pages Between Folders

```
PATCH /api/v1/pages/{page_id}/
{ "folder_id": "fld_abc" }
```

Set `folder_id` to `null` to move to project root.
