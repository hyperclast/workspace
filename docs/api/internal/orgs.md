# Organizations API

## Table of Contents

- [List all organizations](#list-all-organizations)
- [Get a specific organization](#get-a-specific-organization)
- [Create a new organization](#create-a-new-organization)
- [Update an organization](#update-an-organization)
- [Delete an organization](#delete-an-organization)
- [List organization members](#list-organization-members)
- [Add organization member](#add-organization-member)
- [Remove organization member](#remove-organization-member)
- [Update member role](#update-member-role)
- [Autocomplete organization members](#autocomplete-organization-members)

## List all organizations

Retrieve all organizations that the authenticated user is a member of.

### URL

`/api/orgs/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

None

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
    "external_id": "org123",
    "name": "My Organization",
    "domain": "myorg.com",
    "created": "2025-01-10T08:00:00Z"
  },
  {
    "external_id": "org456",
    "name": "Another Org",
    "domain": "anotherorg.com",
    "created": "2025-01-05T09:00:00Z"
  }
]
```

**Notes:**

- Returns only organizations where the user is a member
- Organizations are returned in database order (not sorted)
- The `domain` field may be `null` if not set

---

## Get a specific organization

Retrieve a single organization by its external ID.

### URL

`/api/orgs/{external_id}/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the organization

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be a member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "org123",
  "name": "My Organization",
  "domain": "myorg.com",
  "created": "2025-01-10T08:00:00Z"
}
```

**Error Responses:**

- Status Code: 404 - Organization not found or user is not a member

---

## Create a new organization

Create a new organization. The authenticated user automatically becomes an admin member.

### URL

`/api/orgs/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `name` (String, required): The organization name.

### Authorization

Requires authentication. See [Overview](./overview.md) for details.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "external_id": "org123",
  "name": "My New Organization",
  "domain": null,
  "created": "2025-01-15T10:30:00Z"
}
```

**Notes:**

- The authenticated user is automatically added as an admin member
- The `domain` field is initially `null` and can be set later
- A unique `external_id` is automatically generated

**Example Request:**

```json
{
  "name": "My New Organization"
}
```

---

## Update an organization

Update an organization's details. Only admins can update organizations.

### URL

`/api/orgs/{external_id}/`

### HTTP Method

`PATCH`

### Path Params

- `external_id` (String, required): The external ID of the organization

### Query Params

None

### Data Params

- `name` (String, optional): The new organization name.

### Authorization

Requires authentication. User must be an admin member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "org123",
  "name": "Updated Organization Name",
  "domain": "myorg.com",
  "created": "2025-01-10T08:00:00Z"
}
```

**Error Responses:**

- Status Code: 403 - User is not an admin of the organization
- Status Code: 404 - Organization not found

**Example Request:**

```json
{
  "name": "Updated Organization Name"
}
```

---

## Delete an organization

Permanently delete an organization. Only admins can delete organizations.

### URL

`/api/orgs/{external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the organization

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be an admin member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- This is a permanent delete (hard delete), not a soft delete
- Deleting an organization will cascade delete all related data (projects, pages, memberships, etc.)
- Use with caution - this action cannot be undone

**Error Responses:**

- Status Code: 403 - User is not an admin of the organization
- Status Code: 404 - Organization not found

---

## List organization members

Retrieve all members of an organization.

### URL

`/api/orgs/{external_id}/members/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the organization

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be a member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
[
  {
    "external_id": "user123",
    "email": "admin@example.com",
    "role": "admin",
    "created": "2025-01-10T08:00:00Z"
  },
  {
    "external_id": "user456",
    "email": "member@example.com",
    "role": "member",
    "created": "2025-01-11T09:00:00Z"
  }
]
```

**Notes:**

- Returns all members of the organization
- The `role` field can be either `"admin"` or `"member"`
- Members are returned in database order (not sorted)
- The `created` timestamp indicates when the membership was created

**Error Responses:**

- Status Code: 404 - Organization not found or user is not a member

---

## Add organization member

Add a user as a member of the organization. Any existing member can invite new members.

### URL

`/api/orgs/{external_id}/members/`

### HTTP Method

`POST`

### Path Params

- `external_id` (String, required): The external ID of the organization

### Query Params

None

### Data Params

- `email` (String, required): Email address of the user to add. Must be a valid email format.
- `role` (String, optional): The role to assign. Must be either `"admin"` or `"member"`. Defaults to `"member"` if not provided.

### Authorization

Requires authentication. User must be a member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "external_id": "user789",
  "email": "newmember@example.com",
  "role": "member",
  "created": "2025-01-15T10:30:00Z"
}
```

**Notes:**

- The user must already exist in the system (have a registered account)
- Any member can add new members - not restricted to admins
- If no role is specified, the user is added as a `"member"`

**Error Responses:**

- Status Code: 400 - User is already a member of the organization
- Status Code: 404 - Organization not found, user not a member, or user with specified email doesn't exist

**Example Request:**

```json
{
  "email": "newmember@example.com",
  "role": "admin"
}
```

---

## Remove organization member

Remove a member from the organization. Any member can remove others or themselves.

### URL

`/api/orgs/{external_id}/members/{user_external_id}/`

### HTTP Method

`DELETE`

### Path Params

- `external_id` (String, required): The external ID of the organization
- `user_external_id` (String, required): The external ID of the user to remove

### Query Params

None

### Data Params

None

### Authorization

Requires authentication. User must be a member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 204 (No Content)

**Notes:**

- Any member can remove any other member
- Members can remove themselves
- Cannot remove the only admin - will return 400 error if attempted
- Removing a member immediately revokes their access to all organization resources

**Error Responses:**

- Status Code: 400 - Attempted to remove the only admin
- Status Code: 404 - Organization not found, user not a member, or user to remove is not a member

---

## Update member role

Update a member's role within the organization. Only admins can change roles.

### URL

`/api/orgs/{external_id}/members/{user_external_id}/`

### HTTP Method

`PATCH`

### Path Params

- `external_id` (String, required): The external ID of the organization
- `user_external_id` (String, required): The external ID of the user whose role to update

### Query Params

None

### Data Params

- `role` (String, required): The new role. Must be either `"admin"` or `"member"`.

### Authorization

Requires authentication. User must be an admin of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "user456",
  "email": "member@example.com",
  "role": "admin",
  "created": "2025-01-11T09:00:00Z"
}
```

**Notes:**

- Only admins can change member roles
- Cannot demote yourself if you're the only admin - will return 400 error

**Error Responses:**

- Status Code: 400 - Attempted to demote the only admin
- Status Code: 403 - User is not an admin of the organization
- Status Code: 404 - Organization not found or user to update is not a member

**Example Request:**

```json
{
  "role": "admin"
}
```

---

## Autocomplete organization members

Search for organization members by username or email for @mention autocomplete functionality.

### URL

`/api/orgs/{external_id}/members/autocomplete/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the organization

### Query Params

- `q` (String, optional): Search query to filter members by username or email (case-insensitive). Default: "" (returns all members)

### Data Params

None

### Authorization

Requires authentication. User must be a member of the organization.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "members": [
    {
      "external_id": "user123",
      "username": "alice",
      "email": "alice@example.com"
    },
    {
      "external_id": "user456",
      "username": "bob",
      "email": "bob@example.com"
    }
  ]
}
```

**Notes:**

- Returns members of the specified organization that match the search query
- Search is case-insensitive and matches partial usernames or emails
- Maximum of 10 results are returned
- Empty query (`q=""` or no `q` parameter) returns all members (up to 10)
- Used primarily for @mention autocomplete in the editor

**Example Usage:**

```bash
# Search for members with "alice" in username or email
GET /api/orgs/org123/members/autocomplete/?q=alice

# Get all members (up to 10)
GET /api/orgs/org123/members/autocomplete/
```

**Error Responses:**

- Status Code: 404 - Organization not found or user is not a member
