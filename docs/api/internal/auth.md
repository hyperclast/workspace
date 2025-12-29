# Authentication API

## Table of Contents

- [Overview](#overview)
- [Get session status](#get-session-status)
- [Login](#login)
- [Signup](#signup)
- [Logout](#logout)
- [Request password reset](#request-password-reset)
- [Reset password](#reset-password)

## Overview

The following docs include the allauth-headless API endpoints used by the SPA for handling/managing authentication.

The URLs, request/response payloads, and flows are unchanged from the allauth-headless defaults.

Ref: https://docs.allauth.org/en/dev/headless/openapi-specification/#section/App-Usage/Access-Tokens

## Get session status

Check the current authentication status and retrieve user information.

### URL

`/api/browser/v1/auth/session`

### HTTP Method

`GET`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

No authentication required. Returns session status for both authenticated and unauthenticated users.

### Request Headers

```
Content-Type: application/json
```

### Response

- Status Code: 200
- Schema:

```json
{
  "meta": {
    "is_authenticated": true
  },
  "data": {
    "user": {
      "external_id": 123,
      "email": "user@example.com"
    }
  }
}
```

**Notes:**

- `meta.is_authenticated` is `true` if user is logged in, `false` otherwise
- `data.user` contains user information when authenticated, `null` when not authenticated
- This endpoint is used to initialize the CSRF token and check authentication status

---

## Login

Authenticate a user with email and password.

### URL

`/api/browser/v1/auth/login`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `email` (String, required): User's email address
- `password` (String, required): User's password

### Authorization

No authentication required.

### Request Headers

```
Content-Type: application/json
X-CSRFToken: YOUR_CSRF_TOKEN
```

### Response

**Success:**

- Status Code: 200
- Schema:

```json
{
  "meta": {
    "is_authenticated": true
  },
  "data": {
    "user": {
      "external_id": 123,
      "email": "user@example.com"
    }
  }
}
```

**Error:**

- Status Code: 200 (with `is_authenticated: false`) or 400
- Schema:

```json
{
  "meta": {
    "is_authenticated": false
  },
  "errors": [
    {
      "message": "The email address and/or password you specified are not correct."
    }
  ]
}
```

**Notes:**

- Successfully authenticates the user and creates a session
- Session cookie is set automatically by the browser
- Check `meta.is_authenticated` to determine if login was successful

---

## Signup

Create a new user account with email and password.

### URL

`/api/browser/v1/auth/signup`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `email` (String, required): User's email address. Must be a valid email format.
- `password` (String, required): User's password. Must be at least 8 characters long.

### Authorization

No authentication required.

### Request Headers

```
Content-Type: application/json
X-CSRFToken: YOUR_CSRF_TOKEN
```

### Response

**Success:**

- Status Code: 200
- Schema:

```json
{
  "meta": {
    "is_authenticated": true
  },
  "data": {
    "user": {
      "external_id": 123,
      "email": "user@example.com"
    }
  }
}
```

**Error:**

- Status Code: 200 (with `is_authenticated: false`) or 400
- Schema:

```json
{
  "meta": {
    "is_authenticated": false
  },
  "errors": [
    {
      "message": "A user is already registered with this email address."
    }
  ]
}
```

**Notes:**

- Successfully creates a new user account and logs them in
- Session cookie is set automatically by the browser
- Password must meet the minimum length requirement (8 characters)
- Email must be unique and not already registered

---

## Logout

End the current user session.

### URL

`/api/browser/v1/auth/session`

### HTTP Method

`DELETE`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

Requires authentication.

### Request Headers

```
Content-Type: application/json
X-CSRFToken: YOUR_CSRF_TOKEN
```

### Response

- Status Code: 200
- Schema:

```json
{
  "meta": {
    "is_authenticated": false
  }
}
```

**Notes:**

- Destroys the current session
- Session cookie is invalidated
- User must log in again to access protected resources

---

## Request password reset

Request a password reset email to be sent to the specified email address.

### URL

`/api/browser/v1/auth/password/request`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `email` (String, required): Email address to send the password reset link to

### Authorization

No authentication required.

### Request Headers

```
Content-Type: application/json
X-CSRFToken: YOUR_CSRF_TOKEN
```

### Response

- Status Code: 200
- Schema:

```json
{
  "meta": {
    "is_authenticated": false
  }
}
```

**Notes:**

- For security reasons, this endpoint returns 200 even if the email doesn't exist
- This prevents attackers from enumerating valid email addresses
- If the email exists, a password reset link is sent to that address
- The reset link contains a one-time use token with an expiration time

---

## Reset password

Reset a user's password using a reset token.

This is a two-step process:

1. Validate the reset key with a GET request
2. Submit the new password with a POST request

### URL

`/api/browser/v1/auth/password/reset`

### HTTP Method (Step 1)

`GET`

### Path Params

None

### Query Params

None

### Data Params

None

### Authorization

No authentication required, but requires valid reset key in header.

### Request Headers (Step 1)

```
X-Password-Reset-Key: RESET_KEY_FROM_EMAIL
```

### Response (Step 1)

**Success:**

- Status Code: 200
- Schema:

```json
{
  "meta": {
    "is_authenticated": false
  }
}
```

**Error:**

- Status Code: 400
- Schema:

```json
{
  "errors": [
    {
      "message": "Invalid or expired reset key"
    }
  ]
}
```

---

### HTTP Method (Step 2)

`POST`

### Path Params

None

### Query Params

None

### Data Params

- `key` (String, required): The password reset key from the email
- `password` (String, required): The new password. Must be at least 8 characters long.

### Authorization

Requires the GET request (Step 1) to have been completed successfully.

### Request Headers (Step 2)

```
Content-Type: application/json
X-CSRFToken: YOUR_CSRF_TOKEN
X-Password-Reset-Key: RESET_KEY_FROM_EMAIL
```

### Response (Step 2)

**Success:**

- Status Code: 200 (user logged in) or 401 (password reset but not logged in)
- Schema (200):

```json
{
  "meta": {
    "is_authenticated": true
  },
  "data": {
    "user": {
      "external_id": 123,
      "email": "user@example.com"
    }
  }
}
```

- Schema (401):

```json
{
  "meta": {
    "is_authenticated": false
  }
}
```

**Error:**

- Status Code: 400
- Schema:

```json
{
  "errors": [
    {
      "message": "Password reset failed. The link may have expired."
    }
  ]
}
```

**Notes:**

- The two-step process is required by django-allauth headless
- Step 1 (GET) validates the reset key and establishes a semi-authenticated session
- Step 2 (POST) actually resets the password
- Both 200 and 401 responses are considered successful password resets
- The reset key can only be used once
- After successful reset, users should be redirected to the login page

**Example Implementation:**

```javascript
// Step 1: Validate reset key
const validateResponse = await fetch("/api/browser/v1/auth/password/reset", {
  method: "GET",
  credentials: "same-origin",
  headers: {
    "X-Password-Reset-Key": resetKey,
  },
});

if (!validateResponse.ok) {
  // Handle validation error
  return;
}

// Read response to ensure session is established
await validateResponse.json();

// Step 2: Submit new password
const response = await fetch("/api/browser/v1/auth/password/reset", {
  method: "POST",
  credentials: "same-origin",
  headers: {
    "Content-Type": "application/json",
    "X-CSRFToken": getCsrfToken(),
    "X-Password-Reset-Key": resetKey,
  },
  body: JSON.stringify({
    key: resetKey,
    password: newPassword,
  }),
});

// Check for success (both 200 and 401 indicate successful reset)
if (response.ok || response.status === 401) {
  // Redirect to login
  window.location.href = "/login";
}
```
