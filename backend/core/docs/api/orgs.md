# Organizations

Organizations are team workspaces containing projects and pages. Members can have `admin` or `member` roles.

| Role     | Permissions                                               |
| -------- | --------------------------------------------------------- |
| `admin`  | Full control: update settings, delete org, manage members |
| `member` | View org, create projects, invite members                 |

---

## List Organizations

Get all organizations you're a member of.

|              |                  |
| ------------ | ---------------- |
| **Endpoint** | `GET /api/orgs/` |
| **Auth**     | Bearer token     |

**Response (200):**

```json
[
  {
    "external_id": "org123",
    "name": "My Organization",
    "domain": "myorg.com",
    "is_pro": true,
    "created": "2025-01-10T08:00:00Z",
    "modified": "2025-01-12T14:30:00Z"
  }
]
```

| Field      | Description                                      |
| ---------- | ------------------------------------------------ |
| `is_pro`   | Whether the org has an active paid subscription  |
| `modified` | Last time the organization settings were changed |

---

## Get Organization

|              |                                |
| ------------ | ------------------------------ |
| **Endpoint** | `GET /api/orgs/{external_id}/` |
| **Auth**     | Bearer token                   |

**Response (200):**

```json
{
  "external_id": "org123",
  "name": "My Organization",
  "domain": "myorg.com",
  "is_pro": true,
  "created": "2025-01-10T08:00:00Z",
  "modified": "2025-01-12T14:30:00Z"
}
```

---

## Create Organization

You'll automatically be added as an admin.

|              |                   |
| ------------ | ----------------- |
| **Endpoint** | `POST /api/orgs/` |
| **Auth**     | Bearer token      |

| Field  | Type   | Required? | Description       |
| ------ | ------ | --------- | ----------------- |
| `name` | string | Yes       | Organization name |

**Response (201):**

```json
{
  "external_id": "org789",
  "name": "My New Organization",
  "domain": null,
  "is_pro": false,
  "created": "2025-01-15T14:30:00Z",
  "modified": "2025-01-15T14:30:00Z"
}
```

> New organizations start with `is_pro: false`.

---

## Update Organization

|              |                                  |
| ------------ | -------------------------------- |
| **Endpoint** | `PATCH /api/orgs/{external_id}/` |
| **Auth**     | Bearer token (admin only)        |

| Field  | Type   | Required? | Description           |
| ------ | ------ | --------- | --------------------- |
| `name` | string | No        | New organization name |

**Response (200):**

```json
{
  "external_id": "org123",
  "name": "Updated Organization Name",
  "domain": "myorg.com",
  "is_pro": true,
  "created": "2025-01-10T08:00:00Z",
  "modified": "2025-01-15T11:00:00Z"
}
```

**Error Responses:**

| Status | Reason                                         |
| ------ | ---------------------------------------------- |
| 403    | You are a member but not an admin              |
| 404    | Organization not found or you are not a member |

---

## Delete Organization

Permanently deletes the organization and all its projects/pages.

|              |                                   |
| ------------ | --------------------------------- |
| **Endpoint** | `DELETE /api/orgs/{external_id}/` |
| **Auth**     | Bearer token (admin only)         |

**Response (204):** No content.

> **Warning:** This cannot be undone.

**Error Responses:**

| Status | Reason                                         |
| ------ | ---------------------------------------------- |
| 403    | You are a member but not an admin              |
| 404    | Organization not found or you are not a member |

---

## Members

### List Members

|              |                                        |
| ------------ | -------------------------------------- |
| **Endpoint** | `GET /api/orgs/{external_id}/members/` |
| **Auth**     | Bearer token                           |

**Response (200):**

```json
[
  {
    "external_id": "user123",
    "email": "admin@example.com",
    "username": "admin_user",
    "role": "admin",
    "created": "2025-01-10T08:00:00Z"
  },
  {
    "external_id": "user456",
    "email": "member@example.com",
    "username": "member_user",
    "role": "member",
    "created": "2025-01-12T14:30:00Z"
  }
]
```

| Field     | Description                            |
| --------- | -------------------------------------- |
| `role`    | `admin` or `member`                    |
| `created` | When this user joined the organization |

### Add Member

|              |                                         |
| ------------ | --------------------------------------- |
| **Endpoint** | `POST /api/orgs/{external_id}/members/` |
| **Auth**     | Bearer token                            |

| Field   | Type   | Required? | Description                      |
| ------- | ------ | --------- | -------------------------------- |
| `email` | string | Yes       | User's email (must have account) |
| `role`  | string | No        | `admin` or `member` (default)    |

**Response (201):**

```json
{
  "external_id": "user789",
  "email": "newmember@example.com",
  "username": "newmember",
  "role": "member",
  "created": "2025-01-15T14:30:00Z"
}
```

> **Note:** Org member invitations require the user to already have an account. Rate limited: 1/10s burst, 100/day.

### Update Member Role

|              |                                                    |
| ------------ | -------------------------------------------------- |
| **Endpoint** | `PATCH /api/orgs/{external_id}/members/{user_id}/` |
| **Auth**     | Bearer token (admin only)                          |

| Field  | Type   | Required? | Description         |
| ------ | ------ | --------- | ------------------- |
| `role` | string | Yes       | `admin` or `member` |

**Response (200):**

```json
{
  "external_id": "user456",
  "email": "member@example.com",
  "username": "member_user",
  "role": "admin",
  "created": "2025-01-12T14:30:00Z"
}
```

**Error Responses:**

| Status | Reason                                                                 |
| ------ | ---------------------------------------------------------------------- |
| 400    | Cannot demote the only admin                                           |
| 403    | You are a member but not an admin                                      |
| 404    | Organization not found, you are not a member, or target user not found |

### Remove Member

|              |                                                     |
| ------------ | --------------------------------------------------- |
| **Endpoint** | `DELETE /api/orgs/{external_id}/members/{user_id}/` |
| **Auth**     | Bearer token                                        |

**Response (204):** No content.

**Permission Rules:**

- Admins can remove any member (including other admins)
- Non-admins can remove other non-admins
- Non-admins cannot remove admins (returns 403)
- Cannot remove the only admin (returns 400)

### Autocomplete Members

Search for org members by username or email. Used for @mention autocomplete.

|              |                                                     |
| ------------ | --------------------------------------------------- |
| **Endpoint** | `GET /api/orgs/{external_id}/members/autocomplete/` |
| **Auth**     | Bearer token                                        |

**Query:** `?q=search+term`

**Response (200):**

```json
{
  "members": [
    {
      "external_id": "user123",
      "username": "alice",
      "email": "alice@example.com"
    }
  ]
}
```

**Notes:**

- Returns up to 10 matching members
- Case-insensitive search on username and email
- Empty query returns all members (up to 10)

---

## Examples

### List your organizations

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/orgs/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/orgs/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/orgs/`, {
  headers: { Authorization: `Bearer ${TOKEN}` },
});
console.log(await response.json());
```

```ruby
require 'net/http'
require 'json'
require 'uri'

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

uri = URI("#{BASE_URL}/api/orgs/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Get.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";

$ch = curl_init("$baseUrl/api/orgs/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => ["Authorization: Bearer $token"]
]);
$response = curl_exec($ch);
curl_close($ch);
print_r(json_decode($response, true));
```

```go
package main

import (
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL = "<BASE_URL>"
    token   = "<ACCESS_TOKEN>"
)

func main() {
    req, _ := http.NewRequest("GET", baseURL+"/api/orgs/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result []map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Create an organization

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl -X POST "$BASE_URL/api/orgs/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "name": "My New Organization"
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.post(
    f"{BASE_URL}/api/orgs/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"name": "My New Organization"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/orgs/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ name: "My New Organization" }),
});
console.log(await response.json());
```

```ruby
require 'net/http'
require 'json'
require 'uri'

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

uri = URI("#{BASE_URL}/api/orgs/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = { name: "My New Organization" }.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";

$ch = curl_init("$baseUrl/api/orgs/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode(["name" => "My New Organization"])
]);
$response = curl_exec($ch);
curl_close($ch);
print_r(json_decode($response, true));
```

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL = "<BASE_URL>"
    token   = "<ACCESS_TOKEN>"
)

func main() {
    body, _ := json.Marshal(map[string]string{"name": "My New Organization"})

    req, _ := http.NewRequest("POST", baseURL+"/api/orgs/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Add a member

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
ORG_ID="org123"

curl -X POST "$BASE_URL/api/orgs/$ORG_ID/members/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "email": "newmember@example.com",
  "role": "member"
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
ORG_ID = "org123"

response = requests.post(
    f"{BASE_URL}/api/orgs/{ORG_ID}/members/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"email": "newmember@example.com", "role": "member"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const ORG_ID = "org123";

const response = await fetch(`${BASE_URL}/api/orgs/${ORG_ID}/members/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    email: "newmember@example.com",
    role: "member",
  }),
});
console.log(await response.json());
```

```ruby
require 'net/http'
require 'json'
require 'uri'

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
ORG_ID = "org123"

uri = URI("#{BASE_URL}/api/orgs/#{ORG_ID}/members/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = { email: "newmember@example.com", role: "member" }.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$orgId = "org123";

$ch = curl_init("$baseUrl/api/orgs/$orgId/members/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "email" => "newmember@example.com",
        "role" => "member"
    ])
]);
$response = curl_exec($ch);
curl_close($ch);
print_r(json_decode($response, true));
```

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL = "<BASE_URL>"
    token   = "<ACCESS_TOKEN>"
    orgID   = "org123"
)

func main() {
    body, _ := json.Marshal(map[string]string{
        "email": "newmember@example.com",
        "role":  "member",
    })

    req, _ := http.NewRequest("POST", baseURL+"/api/orgs/"+orgID+"/members/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```
