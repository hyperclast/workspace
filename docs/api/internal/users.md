# Users API

## Table of Contents

- [Get current user](#get-current-user)
- [Get access token](#get-access-token)
- [Regenerate access token](#regenerate-access-token)
- [Get storage summary](#get-storage-summary)
- [Create Stripe checkout session](#create-stripe-checkout-session)
- [Update user settings](#update-user-settings)

## Get current user

Get the current authenticated user's information. Used by the frontend to check authentication status.

### URL

`/api/users/me/`

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
- The token can be regenerated from the Settings page or via the `/api/users/me/token/regenerate/` endpoint

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "message": "Not authenticated"
}
```

---

## Get access token

Retrieve the user's API access token. Useful for displaying the token in the UI (e.g., Settings page).

### URL

`/api/users/me/token/`

### HTTP Method

`GET`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

Requires session-based authentication.

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
  "message": "Not authenticated"
}
```

---

## Regenerate access token

Generate a new API access token, immediately invalidating the old one. Useful for token rotation or when a token has been compromised.

### URL

`/api/users/me/token/regenerate/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

Requires session-based authentication.

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
  "message": "Not authenticated"
}
```

**Example Usage:**

```javascript
// From the SPA Settings page
const response = await csrfFetch("/api/users/me/token/regenerate/", {
  method: "POST",
});

if (response.ok) {
  const data = await response.json();
  console.log("New token:", data.access_token);
  // Update UI to show new token
}
```

---

## Get storage summary

Get the total storage used by the current user. Returns the sum of all file sizes and count of files uploaded by the user.

### URL

`/api/users/storage/`

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
- `total_bytes` is the sum of all file sizes in bytes
- `file_count` is the total number of files

**Error Responses:**

- Status Code: 401 - Not authenticated

```json
{
  "message": "Not authenticated"
}
```

---

## Create Stripe checkout session

Create a Stripe checkout session ID for subscribing to a plan.

### URL

`/api/users/stripe/checkout/`

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
  "message": "Unauthorized"
}
```

- Status Code: 400 - Error creating checkout session

```json
{
  "message": "Unexpected error"
}
```

---

## Update user settings

Update the current user's profile settings.

### URL

`/api/users/settings/`

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
  "message": "Unauthorized"
}
```

- Status Code: 400 - Error updating settings

```json
{
  "message": "Unexpected error"
}
```
