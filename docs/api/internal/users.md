# Users API

## Table of Contents

- [Get current user](#get-current-user)
- [Get access token](#get-access-token)
- [Regenerate access token](#regenerate-access-token)
- [List access tokens](#list-access-tokens)
- [Create access token](#create-access-token)
- [Retrieve access token](#retrieve-access-token)
- [Update access token](#update-access-token)
- [Get storage summary](#get-storage-summary)
- [Create Stripe checkout session](#create-stripe-checkout-session)
- [Update user settings](#update-user-settings)

## Get current user

Get the current authenticated user's information. Used by the frontend to check authentication status.

### URL

`/api/v1/users/me/`

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
{
  "external_id": "abc123",
  "email": "user@example.com",
  "is_authenticated": true,
  "access_token": "NhqPaZgfmRLxcBvYS..."
}
```

**Notes:**

- The `access_token` field contains the user's API access token for external client access
- This token can be used with bearer authentication for programmatic API access
- The token can be regenerated from the Settings page or via the `/api/v1/users/me/token/regenerate/` endpoint

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "error": "error",
  "message": "Unauthorized",
  "detail": "Unauthorized"
}
```

---

## Get access token

Retrieve the user's default API access token. Useful for displaying the token in the UI (e.g., Settings page). Returns the value of the user's default `AccessToken`.

### URL

`/api/v1/users/me/token/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

Requires authentication (bearer token, X-Session-Token, or session).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "access_token": "NhqPaZgfmRLxcBvYS..."
}
```

**Notes:**

- This endpoint returns only the access token
- Used by the Settings page to display the token to users
- Requires session authentication (not bearer token)

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "error": "error",
  "message": "Unauthorized",
  "detail": "Unauthorized"
}
```

---

## Regenerate access token

Generate a new default API access token, immediately invalidating the old one. Useful for token rotation or when a token has been compromised. Operates on the user's default `AccessToken` row.

### URL

`/api/v1/users/me/token/regenerate/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

Requires authentication (bearer token, X-Session-Token, or session).

### Request Headers

See [Overview](./overview.md)

**CSRF Token Required:** This endpoint requires a valid CSRF token in the `X-CSRFToken` header for POST requests.

### Response

- Status Code: 200
- Schema:

```json
{
  "access_token": "dGhpcyBpcyBhIG5ldyB0b2tlbg..."
}
```

**Notes:**

- The old token is **immediately invalidated** when the new token is generated
- Any external clients using the old token will need to be updated with the new token
- This is a destructive operation and cannot be undone
- Used by the Settings page "Regenerate Token" button

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "error": "error",
  "message": "Unauthorized",
  "detail": "Unauthorized"
}
```

**Example Usage:**

```javascript
// From the SPA Settings page
const response = await csrfFetch("/api/v1/users/me/token/regenerate/", {
  method: "POST",
});

if (response.ok) {
  const data = await response.json();
  console.log("New token:", data.access_token);
  // Update UI to show new token
}
```

---

## List access tokens

List all user-managed access tokens for the current user, ordered by creation date (newest first).

### URL

`/api/v1/users/me/tokens/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

Requires authentication (bearer token or session).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
[
  {
    "external_id": "abc123",
    "value": "NhqPaZgfmRLxcBvYS...",
    "label": "Default",
    "is_default": true,
    "is_active": true,
    "created": "2025-01-15T10:30:00Z"
  }
]
```

**Notes:**

- Only returns user-managed tokens (not system-managed device tokens)
- Returns full token values (not masked)

**Error Responses:**

- Status Code: 401 - Not authenticated

---

## Create access token

Create a new user-managed access token with a custom label.

### URL

`/api/v1/users/me/tokens/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `label` (String, required): A label for the token. 1-255 characters.

### Authorization

Requires authentication (bearer token or session).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 201
- Schema:

```json
{
  "external_id": "def456",
  "value": "dGhpcyBpcyBhIG5ldyB0b2tlbg...",
  "label": "CI Pipeline",
  "is_default": false,
  "is_active": true,
  "created": "2025-01-15T10:30:00Z"
}
```

**Notes:**

- New tokens are always created with `is_default: false` and `is_active: true`
- The token value is auto-generated and returned in the response

**Error Responses:**

- Status Code: 401 - Not authenticated
- Status Code: 422 - Validation error (missing or invalid label)

---

## Retrieve access token

Get a specific user-managed access token by its external ID.

### URL

`/api/v1/users/me/tokens/{external_id}/`

### HTTP Method

`GET`

### Path Params

- `external_id` (String, required): The external ID of the token

### Query Params

None

### Data Params

None

### Authorization

Requires authentication (bearer token or session).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "abc123",
  "value": "NhqPaZgfmRLxcBvYS...",
  "label": "Default",
  "is_default": true,
  "is_active": true,
  "created": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**

- Status Code: 401 - Not authenticated
- Status Code: 404 - Token not found (wrong ID, belongs to another user, or is a system-managed token)

---

## Update access token

Update a user-managed access token's label or active status.

### URL

`/api/v1/users/me/tokens/{external_id}/`

### HTTP Method

`PATCH`

### Path Params

- `external_id` (String, required): The external ID of the token

### Query Params

None

### Data Params

Only include the fields you want to update:

- `label` (String, optional): New label. 1-255 characters.
- `is_active` (Boolean, optional): Set to `false` to deactivate, `true` to reactivate.

### Authorization

Requires authentication (bearer token or session).

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "external_id": "def456",
  "value": "dGhpcyBpcyBhIG5ldyB0b2tlbg...",
  "label": "Renamed Token",
  "is_default": false,
  "is_active": false,
  "created": "2025-01-15T10:30:00Z"
}
```

**Notes:**

- Cannot deactivate the default token (returns 400)
- Cannot set `is_default` via this endpoint

**Error Responses:**

- Status Code: 400 - Cannot deactivate the default token
- Status Code: 401 - Not authenticated
- Status Code: 404 - Token not found
- Status Code: 422 - Validation error

---

## Get storage summary

Get the total storage used by the current user. Returns the sum of all file sizes and count of files uploaded by the user.

### URL

`/api/v1/users/storage/`

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
{
  "total_bytes": 15728640,
  "file_count": 12
}
```

**Notes:**

- Only counts files in `AVAILABLE` status (completed uploads)
- Only counts files uploaded by the authenticated user
- `total_bytes` is the sum of all file sizes in bytes (uses verified `actual_size` when available, falls back to `expected_size`)
- `file_count` is the total number of files

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "error": "error",
  "message": "Unauthorized",
  "detail": "Unauthorized"
}
```

---

## Create Stripe checkout session

Create a Stripe checkout session ID for subscribing to a plan.

### URL

`/api/v1/users/stripe/checkout/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `plan` (String, required): The plan identifier to subscribe to

### Authorization

Requires authentication. See [Overview](./overview.md) for details.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "message": "ok",
  "session_id": "cs_test_a1b2c3d4..."
}
```

**Notes:**

- The `session_id` should be used with Stripe's frontend library to redirect the user to the checkout page
- The plan parameter should match one of the configured plan identifiers in the backend

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "error": "error",
  "message": "Unauthorized",
  "detail": "Unauthorized"
}
```

- Status Code: 400 - Error creating checkout session

```json
{
  "error": "error",
  "message": "Unexpected error",
  "detail": null
}
```

---

## Update user settings

Update the current user's profile settings.

### URL

`/api/v1/users/settings/`

### HTTP Method

`PATCH`

### Path Params

None

### Query Params

None

### Data Params

Only include the fields you want to update:

- `tz` (String, optional): Timezone identifier (e.g., "America/New_York", "UTC"). Can be null.

### Authorization

Requires authentication. See [Overview](./overview.md) for details.

### Request Headers

See [Overview](./overview.md)

### Response

- Status Code: 200
- Schema:

```json
{
  "message": "ok",
  "details": {
    "updated_fields": {
      "tz": "America/New_York"
    }
  }
}
```

**Notes:**

- Only fields included in the request body will be updated
- If no fields are updated, the response will only contain `{"message": "ok"}`
- The `details` object is only included if fields were actually updated

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "error": "error",
  "message": "Unauthorized",
  "detail": "Unauthorized"
}
```

- Status Code: 400 - Error updating settings

```json
{
  "error": "error",
  "message": "Unexpected error",
  "detail": null
}
```
