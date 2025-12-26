# Overview

## Table of Contents

- [Base URL](#base-url)
- [Authentication](#authentication)
- [Request Headers](#request-headers)
- [Responses](#responses)
- [Rate Limiting](#rate-limiting)
- [Timestamps](#timestamps)
- [Pagination](#pagination)
- [Available API Resources](#available-api-resources)

## Base URL

All API endpoints are relative to the Hyperclast instance:

```
https://hyperclast.com/api/
```

For local development:

```
http://localhost:9800/api/
```

See the project README for setting the root URL.

## Authentication

### Session-based Authentication (Primary)

Hyperclast API uses Django session-based authentication as the primary authentication method.

**Authentication Flow**

Hyperclast uses django-allauth headless auth to handle/manage authentication for regular users entirely in the SPA:

1. The SPA logs a user in via the web interface (or `/api/browser/v1/auth/login` endpoint)
2. Django creates a session and sets a `sessionid` cookie
3. All subsequent API requests automatically include the session cookie
4. The backend validates the session for each request

**Requirements:**

- User must be logged in through the SPA
- Session cookie must be included in requests (handled automatically by browsers)
- CSRF token must be included for state-changing requests (POST, PUT, PATCH, DELETE)

### Token-based Authentication (Optional)

Some endpoints support optional token-based authentication. But this isn't currently being used in any user-facing API endpoints.

**Authentication Flow:**

1. Obtain an API token from user settings or backend configuration
2. Include the token in the `Authorization` header: `Bearer AUTH_TOKEN`

**Note:** Most endpoints require session authentication. Token authentication is only available for specific endpoints as noted in their documentation.

## Request Headers

### Required Headers

All API requests should include the following header:

```
Content-Type: application/json
```

### CSRF Token (for state-changing requests)

POST, PUT, PATCH, and DELETE requests require a CSRF token for security. Include the token in the request header:

```
X-CSRFToken: YOUR_CSRF_TOKEN
```

**How to obtain the CSRF token:**

For session-based requests in the browser, the CSRF token is available via:

1. Django template context: `{{ csrf_token }}`
2. Cookie: `csrftoken` (read via JavaScript)
3. Hidden input field in forms

**Example with Fetch API:**

```javascript
// Get CSRF token from cookie
function getCsrfToken() {
  return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
}

// Make a POST request
fetch('/api/pages/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken(),
  },
  credentials: 'same-origin',
  body: JSON.stringify({
    title: 'My New Page',
  }),
});
```

### Complete Request Example

```http
POST /api/pages/ HTTP/1.1
Host: localhost:9800
Content-Type: application/json
X-CSRFToken: abc123def456...
Cookie: sessionid=xyz789...

{
  "title": "My New Page"
}
```

## Responses

### Success Responses

Successful API responses return appropriate HTTP status codes:

- `200 OK` - Request succeeded (GET, PUT, PATCH)
- `201 Created` - Resource created successfully (POST)
- `204 No Content` - Request succeeded with no response body (DELETE)

### Response Format

Most successful responses return JSON with the data directly or wrapped in a data object:

**Direct format (single resource):**

```json
{
  "external_id": "abc123",
  "title": "My Note",
  "details": {},
  "created": "2025-01-15T10:30:00Z"
}
```

**Paginated format (lists):**

```json
{
  "items": [
    {
      "external_id": "abc123",
      "title": "Note 1"
    },
    {
      "external_id": "def456",
      "title": "Note 2"
    }
  ],
  "count": 2
}
```

### Error Responses

Error responses include appropriate HTTP status codes and a JSON body with error details:

- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

**Error Response Format:**

```json
{
  "message": "Error description",
  "ok": false
}
```

Or for validation errors:

```json
{
  "detail": [
    {
      "loc": ["body", "title"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Common Error Codes:**

- `401 Unauthorized` - Not authenticated or session expired

  ```json
  {
    "message": "Not authenticated"
  }
  ```

- `404 Not Found` - Resource not found or no access

  ```json
  {
    "ok": false,
    "message": "No such item."
  }
  ```

- `400 Bad Request` - Invalid request data
  ```json
  {
    "message": "User already has access to this page"
  }
  ```

## Rate Limiting

Currently, the Hyperclast API does not implement rate limiting.

## Timestamps

All timestamps in API responses are in ISO 8601 format with UTC timezone:

```
2025-01-15T10:30:00Z
```

Example fields:

- `created` - When the resource was first created
- `modified` - When the resource was last modified by a user
- `updated` - When the resource was last updated (includes system updates)

## Pagination

List endpoints support pagination using Django Ninja's built-in pagination with the following query parameters:

- **`limit`** (optional, default: 100, max: 100) - Number of items per page
- **`offset`** (optional, default: 0) - Number of items to skip

**Paginated Response Format:**

```json
{
  "items": [
    // Array of items (up to limit)
  ],
  "count": 150  // Total number of items across all pages
}
```

**Examples:**

```javascript
// Get first 10 pages
fetch('/api/pages/?limit=10&offset=0');

// Get next 10 pages
fetch('/api/pages/?limit=10&offset=10');

// Get first 25 editors for a note
fetch('/api/pages/abc123/editors/?limit=25&offset=0');

// Use default pagination (100 items)
fetch('/api/pages/');
```

**Iterating through pages:**

```javascript
let offset = 0;
const limit = 50;
let allItems = [];

while (true) {
  const response = await fetch(
    `/api/pages/?limit=${limit}&offset=${offset}`,
    { credentials: 'same-origin' }
  );

  const data = await response.json();
  allItems = allItems.concat(data.items);

  // Stop if we've fetched all items
  if (offset + data.items.length >= data.count) {
    break;
  }

  offset += limit;
}
```

## Available API Resources

- [**Ask API**](./ask.md) - AI-powered question answering about your pages using RAG
- [**Authentication API**](./auth.md) - Login, signup, logout, and password reset (django-allauth headless)
- [**Pages API**](./pages.md) - Create, read, update, and delete pages; manage page editors and invitations
- [**Users API**](./users.md) - User information and settings management
