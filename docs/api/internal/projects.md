# Projects API

## Access Model

Projects use a three-tier access control model:

- **Tier 1 (Org)**: User is a member of the project's organization
- **Tier 2 (Project)**: User is a project editor (directly added to project.editors)

Access is granted if ANY tier condition is true (additive/union model).

## Table of Contents

- [List all projects](#list-all-projects)
- [Get a specific project](#get-a-specific-project)
- [Create a new project](#create-a-new-project)
- [Update a project](#update-a-project)
- [Delete a project](#delete-a-project)
- [List project editors](#list-project-editors)
- [Add project editor](#add-project-editor)
- [Remove project editor](#remove-project-editor)
- [Validate project invitation](#validate-project-invitation)

## List all projects

Retrieve all projects the user has access to via org membership or project editor.

### URL

`/api/projects/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

- `org_id` (String, optional): Filter projects by organization external ID. If not provided, returns projects from all organizations the user is a member of.
- `details` (String, optional): If set to `"full"`, includes the list of pages for each project. Otherwise, the `pages` field is `null`.

### Data Params

None

### Authorization

Requires authentication. See [Overview](./overview.md) for details on session-based authentication.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
[
  {
    "external_id": "abc123",
    "name": "My Project",
    "description": "Project description here",
    "version": "",
    "modified": "2025-01-15T10:30:00Z",
    "created": "2025-01-10T08:00:00Z",
    "creator": {
      "external_id": "user123",
      "email": "creator@example.com"
    },
    "org": {
      "external_id": "org123",
      "name": "My Organization",
      "domain": "myorg.com"
    },
    "pages": null
  }
  // Additional projects...
]
```

**With `details=full`:**

```json
[
  {
    "external_id": "abc123",
    "name": "My Project",
    "description": "Project description here",
    "version": "",
    "modified": "2025-01-15T10:30:00Z",
    "created": "2025-01-10T08:00:00Z",
    "creator": {
      "external_id": "user123",
      "email": "creator@example.com"
    },
    "org": {
      "external_id": "org123",
      "name": "My Organization",
      "domain": "myorg.com"
    },
    "pages": [
      {
        "external_id": "page123",
        "title": "Page 1",
        "updated": "2025-01-14T09:00:00Z",
        "modified": "2025-01-14T09:00:00Z",
        "created": "2025-01-12T08:00:00Z"
      },
      {
        "external_id": "page456",
        "title": "Page 2",
        "updated": "2025-01-13T14:30:00Z",
        "modified": "2025-01-13T14:30:00Z",
        "created": "2025-01-11T10:00:00Z"
      }
    ]
  }
]
```

**Notes:**

- Returns projects where user is an org member OR a project editor
- Deleted projects (soft-deleted) are automatically excluded
- When `details=full`, pages are ordered by `updated` timestamp (most recent first)
- Deleted pages are excluded from the `pages` array
- The `version` field is reserved for future use and currently returns an empty string
- The `creator` object contains information about the user who created the project
- The `org` object contains information about the organization that owns the project

**Example Usage:**

```bash
# Get all projects from all organizations
GET /api/projects/

# Get all projects from a specific organization
GET /api/projects/?org_id=org123

# Get all projects with full details including pages
GET /api/projects/?details=full

# Get projects from a specific organization with full details
GET /api/projects/?org_id=org123&details=full
```

---

## Get a specific project

Retrieve a single project by its external ID.

### URL

`/api/projects/{external_id}/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the project

### Query Params

- `details` (String, optional): If set to `"full"`, includes the list of pages for the project. Otherwise, the `pages` field is `null`.

### Data Params

None

### Authorization

Requires authentication. User must be an org member OR a project editor.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123",
  "name": "My Project",
  "description": "Project description here",
  "version": "",
  "modified": "2025-01-15T10:30:00Z",
  "created": "2025-01-10T08:00:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization",
    "domain": "myorg.com"
  },
  "pages": null
}
```

**With `details=full`:**

```json
{
  "external_id": "abc123",
  "name": "My Project",
  "description": "Project description here",
  "version": "",
  "modified": "2025-01-15T10:30:00Z",
  "created": "2025-01-10T08:00:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization",
    "domain": "myorg.com"
  },
  "pages": [
    {
      "external_id": "page123",
      "title": "Page 1",
      "updated": "2025-01-14T09:00:00Z",
      "modified": "2025-01-14T09:00:00Z",
      "created": "2025-01-12T08:00:00Z"
    }
  ]
}
```

**Error Responses:**

- Status Code: 404 - Project not found, project is deleted, or user has no access (not an org member or project editor)

---

## Create a new project

Create a new project in an organization.

### URL

`/api/projects/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `org_id` (String, required): The external ID of the organization where the project will be created
- `name` (String, required): The project name. Must be 1-255 characters long.
- `description` (String, optional): The project description. Defaults to empty string if not provided.

### Authorization

Requires authentication. User must be a member of the specified organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "external_id": "abc123",
  "name": "New Project",
  "description": "Project description",
  "version": "",
  "modified": "2025-01-15T10:30:00Z",
  "created": "2025-01-15T10:30:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization",
    "domain": "myorg.com"
  },
  "pages": null
}
```

**Notes:**

- The authenticated user becomes the creator of the project
- The `pages` field is always `null` on creation (new projects have no pages)
- Project `version` field is initialized to an empty string

**Error Responses:**

- Status Code: 404 - Organization not found or user is not a member
- Status Code: 422 - Invalid input (e.g., name is empty or too long)

**Example Request:**

```json
{
  "org_id": "org123",
  "name": "My New Project",
  "description": "This is a new project for tracking features"
}
```

---

## Update a project

Update an existing project's name and/or description.

### URL

`/api/projects/{external_id}/`

### HTTP Method

`PATCH`

### Path Params

- `external_id` (String, required): The external ID of the project

### Query Params

None

### Data Params

- `name` (String, optional): The new project name. Must be 1-255 characters long if provided.
- `description` (String, optional): The new project description.

### Authorization

Requires authentication. User must be an org member OR a project editor.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123",
  "name": "Updated Project Name",
  "description": "Updated description",
  "version": "",
  "modified": "2025-01-15T11:00:00Z",
  "created": "2025-01-10T08:00:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization",
    "domain": "myorg.com"
  },
  "pages": null
}
```

**Notes:**

- All fields are optional - you can update just the name, just the description, or both
- The `modified` timestamp is automatically updated
- The `pages` field is always `null` in the response (use `GET /api/projects/{id}/?details=full` to include pages)

**Error Responses:**

- Status Code: 404 - Project not found, project is deleted, or user is not a member of the organization
- Status Code: 422 - Invalid input (e.g., name is empty or too long)

**Example Request:**

```json
{
  "name": "Updated Project Name"
}
```

---

## Delete a project

Soft-delete a project. The project and its pages are marked as deleted but not permanently removed from the database.

### URL

`/api/projects/{external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the project

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be a member of the organization that owns the project.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- This is a soft delete - the project is marked as `is_deleted=True` but not removed from the database
- Deleted projects will not appear in project lists or be accessible via GET requests
- **Only the project creator can delete the project** (org members and project editors cannot delete)

**Error Responses:**

- Status Code: 403 - User is not the project creator
- Status Code: 404 - Project not found, project is already deleted, or user has no access

---

## List project editors

Retrieve all editors for a specific project, including pending invitations.

### URL

`/api/projects/{external_id}/editors/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the project

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have access to the project (org member or project editor).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
[
  {
    "external_id": "user123",
    "email": "editor@example.com",
    "is_creator": false,
    "is_pending": false
  },
  {
    "external_id": "invitation456",
    "email": "pending@example.com",
    "is_creator": false,
    "is_pending": true
  }
]
```

**Notes:**

- Returns both confirmed editors and pending invitations
- `is_creator` is `true` for the user who created the project
- `is_pending` is `true` for users who have been invited but haven't accepted yet
- For pending invitations, `external_id` is the invitation ID (not a user ID)

**Error Responses:**

- Status Code: 404 - Project not found or user has no access

---

## Add project editor

Add a user as an editor to the project. If the user doesn't exist, creates an invitation.

### URL

`/api/projects/{external_id}/editors/`

### HTTP Method

`POST`

### Path Params

- `external_id` (String, required): The external ID of the project

### Query Params

None

### Data Params

- `email` (String, required): Email address of the user to add as editor

### Authorization

Requires authentication. User must have access to the project (org member or project editor).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema (for existing user):

```json
{
  "external_id": "user123",
  "email": "neweditor@example.com",
  "is_creator": false
}
```

- Schema (for new user - invitation created):

```json
{
  "external_id": "invitation456",
  "email": "newuser@example.com",
  "is_creator": false,
  "is_pending": true
}
```

**Notes:**

- If the email belongs to an existing user, they are immediately added as an editor
- If the email doesn't match an existing user, an invitation is created
- An email notification is sent to the invited user
- Re-inviting the same email returns the existing invitation (idempotent)
- Email addresses are normalized to lowercase

**Error Responses:**

- Status Code: 400 - User already has access to this project
- Status Code: 404 - Project not found or user has no access
- Status Code: 422 - Invalid email format

---

## Remove project editor

Remove a user from the project editors or cancel a pending invitation.

### URL

`/api/projects/{external_id}/editors/{user_external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the project
- `user_external_id` (String, required): The external ID of the user to remove, or the invitation ID for pending invitations

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have access to the project (org member or project editor).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- The project creator cannot be removed
- Any editor can remove other editors (including themselves)
- For pending invitations, use the invitation external_id
- An email notification is sent to the removed user
- When a project editor is removed, they immediately lose access to all pages in the project

**Error Responses:**

- Status Code: 400 - Cannot remove the project creator, or user is not an editor
- Status Code: 404 - Project not found, user/invitation not found, or user has no access

---

## Validate project invitation

Validate a project invitation token and return instructions for the frontend.

### URL

`/api/projects/invitations/{token}/validate`

### HTTP Method

`GET`

### Path Params

- `token` (String, required): The invitation token from the invitation URL

### Query Params

None

### Data Params

None

### Authorization

No authentication required (public endpoint).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200 (for valid invitation)
- Schema (authenticated user with matching email - auto-accepts):

```json
{
  "action": "redirect",
  "email": "invited@example.com",
  "redirect_to": "https://app.example.com/?project=abc123",
  "project_name": "My Project"
}
```

- Schema (unauthenticated user):

```json
{
  "action": "signup",
  "email": "invited@example.com",
  "redirect_to": "https://app.example.com/?project=abc123",
  "project_name": "My Project"
}
```

**Notes:**

- For authenticated users with matching email, the invitation is automatically accepted
- For unauthenticated users, the token is stored in the session for auto-acceptance after signup
- The `redirect_to` URL should be used to navigate to the project after authentication
- Accepted invitations cannot be used again

**Error Responses:**

- Status Code: 400 - Invalid invitation (expired, already used, or email mismatch for authenticated user)
