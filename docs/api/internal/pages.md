# Pages API

## Table of Contents

- [Get all editable pages](#get-all-editable-pages)
- [Autocomplete pages](#autocomplete-pages)
- [Create a new page](#create-a-new-page)
- [Get a specific page](#get-a-specific-page)
- [Update a page](#update-a-page)
- [Delete a page](#delete-a-page)
- [Get page links](#get-page-links)
- [Get page editors](#get-page-editors)
- [Add page editor](#add-page-editor)
- [Remove page editor](#remove-page-editor)
- [Validate invitation](#validate-invitation)

## Get all editable pages

Retrieve all pages that the authenticated user can edit (owned pages and shared pages).

### URL

`/api/pages/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

- `limit` (Integer, optional): Number of items to return per page. Default: 100, Max: 100
- `offset` (Integer, optional): Number of items to skip. Default: 0

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
{
  "items": [
    {
      "external_id": "abc123",
      "title": "My Page",
      "details": {
        "content": "Page content here..."
      },
      "updated": "2025-01-15T10:30:00Z",
      "created": "2025-01-10T08:00:00Z",
      "modified": "2025-01-15T10:30:00Z",
      "is_owner": true
    }
    // Additional pages...
  ],
  "count": 10
}
```

**Notes:**

- Pages are ordered by `updated` timestamp (most recent first)
- `is_owner` indicates if the current user owns the page (true) or if it's shared with them (false)
- `details` is a JSON object that can contain arbitrary data; the `content` field stores the page's text
- Use `limit` and `offset` parameters to paginate through large result sets
- The `count` field shows the total number of items across all pages

---

## Autocomplete pages

Search for pages by title for autocomplete/typeahead functionality.

### URL

`/api/pages/autocomplete/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

- `q` (String, optional): Search query to filter pages by title (case-insensitive). Default: "" (returns all pages)

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
{
  "pages": [
    {
      "external_id": "abc123",
      "title": "Python Tutorial",
      "updated": "2025-01-15T10:30:00Z",
      "created": "2025-01-10T08:00:00Z",
      "modified": "2025-01-15T10:30:00Z"
    },
    {
      "external_id": "def456",
      "title": "Python Best Practices",
      "updated": "2025-01-14T14:20:00Z",
      "created": "2025-01-12T09:00:00Z",
      "modified": "2025-01-14T14:20:00Z"
    }
  ]
}
```

**Notes:**

- Returns pages that the user can edit (owned pages and shared pages)
- Search is case-insensitive and matches partial titles
- Results are ordered by `updated` timestamp (most recent first)
- Maximum of 10 results are returned
- Empty query (`q=""` or no `q` parameter) returns all editable pages (up to 10 most recent)
- The `title` field has a database index for improved query performance

**Example Usage:**

```bash
# Search for pages with "python" in the title
GET /api/pages/autocomplete/?q=python

# Get all pages (up to 10 most recent)
GET /api/pages/autocomplete/
```

---

## Create a new page

Create a new page owned by the authenticated user within a project.

### URL

`/api/pages/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `project_id` (String, required): The external ID of the project where the page will be created. User must have access to the project.
- `title` (String, required): The page title. Must be 1-100 characters long.
- `details` (Object, optional): JSON object with arbitrary data. Defaults to `{"content": ""}` if not provided.

### Authorization

Requires authentication. User must have access to the specified project (be a member of the project's organization).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "external_id": "abc123",
  "title": "My New Page",
  "details": {
    "content": ""
  },
  "updated": "2025-01-15T10:30:00Z",
  "created": "2025-01-15T10:30:00Z",
  "modified": "2025-01-15T10:30:00Z",
  "is_owner": true
}
```

**Notes:**

- Pages must belong to a project, which in turn belongs to an organization
- The authenticated user becomes the creator/owner of the page
- The user must be a member of the organization that owns the project

**Error Responses:**

- Status Code: 404 - Project not found or user doesn't have access to the project
- Status Code: 422 - Invalid input (e.g., title is empty or too long)

**Example Request:**

```json
{
  "project_id": "proj123",
  "title": "My New Page",
  "details": {
    "content": "Initial content"
  }
}
```

---

## Get a specific page

Retrieve a single page by its external ID.

### URL

`/api/pages/{external_id}/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the page

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have edit access to the page (owner or shared editor).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123",
  "title": "My Page",
  "details": {
    "content": "Page content here..."
  },
  "updated": "2025-01-15T10:30:00Z",
  "created": "2025-01-10T08:00:00Z",
  "modified": "2025-01-15T10:30:00Z",
  "is_owner": true
}
```

**Error Responses:**

- Status Code: 404 - Note not found or user doesn't have access

---

## Update a page

Update an existing note's title and/or details. Only the owner can use this endpoint to update a page.

### URL

`/api/pages/{external_id}/`

### HTTP Method

`PUT`

### Path Params

- `external_id` (String, required): The external ID of the page

### Query Params

None

### Data Params

- `title` (String, required): The page title. Must be 1-100 characters long.
- `details` (Object, optional): JSON object with arbitrary data. If provided, replaces existing details.

### Authorization

Requires authentication. User must be the owner of the page.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123",
  "title": "Updated Title",
  "details": {
    "content": "Updated content..."
  },
  "updated": "2025-01-15T11:00:00Z",
  "created": "2025-01-10T08:00:00Z",
  "modified": "2025-01-15T11:00:00Z",
  "is_owner": true
}
```

**Error Responses:**

- Status Code: 404 - Note not found or user is not the owner

---

## Delete a page

Delete a page permanently. Only the owner can delete a page.

### URL

`/api/pages/{external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the page

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be the owner of the page.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Error Responses:**

- Status Code: 404 - Note not found or user is not the owner

---

## Get page links

Retrieve outgoing (forward) and incoming (backlinks) internal links for a page.

### URL

`/api/pages/{external_id}/links/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the page

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have edit access to the page.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "outgoing": [
    {
      "external_id": "def456",
      "title": "Linked Page",
      "link_text": "see this page"
    }
  ],
  "incoming": [
    {
      "external_id": "ghi789",
      "title": "Referencing Page",
      "link_text": "My Page"
    }
  ]
}
```

**Notes:**

- `outgoing` contains pages that this page links TO (forward links)
- `incoming` contains pages that link TO this page (backlinks)
- `link_text` is the display text used in the markdown link `[link_text](/pages/...)`
- Links are parsed from page content when saved via collaboration
- Link format: `[Link Text](/pages/{external_id}/)`
- Only links to non-deleted pages are returned
- Indexed for fast lookups (O(log n) on both source and target)

**Example Usage:**

```bash
# Get links for a page
GET /api/pages/abc123/links/
```

**Error Responses:**

- Status Code: 404 - Page not found or user doesn't have access

---

## Get page editors

Retrieve the list of users who have edit access to a page, including the owner and any shared editors.

### URL

`/api/pages/{external_id}/editors/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the page

### Query Params

- `limit` (Integer, optional): Number of items to return per page. Default: 100, Max: 100
- `offset` (Integer, optional): Number of items to skip. Default: 0

### Data Params

None

### Authorization

Requires authentication. User must have edit access to the page.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "items": [
    {
      "external_id": "user123",
      "email": "owner@example.com",
      "is_owner": true,
      "is_pending": false
    },
    {
      "external_id": "user456",
      "email": "editor@example.com",
      "is_owner": false,
      "is_pending": false
    },
    {
      "external_id": "inv789",
      "email": "pending@example.com",
      "is_owner": false,
      "is_pending": true
    }
  ],
  "count": 3
}
```

**Notes:**

- `is_owner` indicates if the user is the page owner
- `is_pending` is true for invitations that haven't been accepted yet
- For pending invitations, `external_id` is the invitation ID (not a user ID)
- Use `limit` and `offset` parameters to paginate through large result sets
- The `count` field shows the total number of editors and pending invitations

**Error Responses:**

- Status Code: 404 - Note not found or user doesn't have access

---

## Add page editor

Add a user as an editor to a page by email address. Any existing editor can add new editors.

### URL

`/api/pages/{external_id}/editors/`

### HTTP Method

`POST`

### Path Params

- `external_id` (String, required): The external ID of the page

### Query Params

None

### Data Params

- `email` (String, required): Email address of the user to add. Must be a valid email format.

### Authorization

Requires authentication. User must have edit access to the page.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema (if user already exists):

```json
{
  "external_id": "user456",
  "email": "editor@example.com",
  "is_owner": false,
  "is_pending": false
}
```

- Schema (if user doesn't exist - invitation created):

```json
{
  "external_id": "inv789",
  "email": "pending@example.com",
  "is_owner": false,
  "is_pending": true
}
```

**Notes:**

- If the email belongs to an existing user, they're immediately added as an editor
- If the email doesn't belong to an existing user, an invitation is created and sent via email
- Invitations are idempotent - sending to the same email multiple times won't create duplicate invitations

**Error Responses:**

- Status Code: 400 - User already has access to this note
- Status Code: 404 - Note not found or current user doesn't have access

---

## Remove page editor

Remove an editor from a page or cancel a pending invitation. Any editor can remove others or themselves, but the owner cannot be removed.

### URL

`/api/pages/{external_id}/editors/{user_external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the page
- `user_external_id` (String, required): The external ID of the user to remove (or invitation ID for pending invitations)

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must have edit access to the page.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- Any editor can remove any other editor (except the owner)
- Editors can remove themselves
- The owner cannot be removed
- Removing an editor immediately revokes their access via WebSocket notification
- For pending invitations, use the invitation `external_id` from the editors list

**Error Responses:**

- Status Code: 400 - Attempted to remove the page owner, or user is not an editor
- Status Code: 404 - Note not found, user doesn't have access, or editor/invitation not found

---

## Validate invitation

Validate an invitation token and determine the appropriate action for the frontend.

### URL

`/api/pages/invitations/{token}/validate`

### HTTP Method

`GET`

### Path Params

- `token` (String, required): The invitation token from the invitation URL

### Query Params

None

### Data Params

None

### Authorization

No authentication required. Works for both authenticated and unauthenticated users.

### Request Headers

Standard headers only (no CSRF token needed for GET requests)

### Response

**For authenticated users with matching email:**

- Status Code: 200
- Schema:

```json
{
  "action": "redirect",
  "email": "invited@example.com",
  "redirect_to": "/?note=abc123",
  "note_title": "Shared Page Title"
}
```

**For unauthenticated users:**

- Status Code: 200
- Schema:

```json
{
  "action": "signup",
  "email": "invited@example.com",
  "redirect_to": "/?note=abc123",
  "note_title": "Shared Page Title"
}
```

**Notes:**

- For authenticated users with matching email: invitation is automatically accepted
- For authenticated users with mismatched email: returns 400 error
- For unauthenticated users: frontend should redirect to signup with pre-filled email
- The invitation token is stored in the session for auto-acceptance after login/signup

**Error Responses:**

- Status Code: 400 - Invalid, expired, or already accepted invitation
- Status Code: 400 - Email mismatch for authenticated users

Example error response:

```json
{
  "error": "invalid_invitation",
  "message": "This invitation is invalid, expired, or has already been accepted."
}
```

```json
{
  "error": "email_mismatch",
  "message": "This invitation is for invited@example.com, but you're logged in as other@example.com."
}
```
