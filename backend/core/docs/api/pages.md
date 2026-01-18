# Pages

Pages are documents within projects. Access is granted through organization membership, project sharing, or direct page sharing.

## Access Control

Access uses an additive three-tier model—access is granted if **any** tier applies:

| Tier    | Description                                           |
| ------- | ----------------------------------------------------- |
| Org     | Org admin, or org member (when enabled)               |
| Project | Added as project editor (editor/viewer role)          |
| Page    | Explicitly shared as page editor (editor/viewer role) |

### Role-Based Permissions

Within each tier, roles control what actions are allowed:

| Role     | Read | Write | Manage Sharing |
| -------- | :--: | :---: | :------------: |
| `editor` |  ✓   |   ✓   |       ✓        |
| `viewer` |  ✓   |       |                |

**Note:** Viewers can read pages but cannot create pages, edit content, generate access codes, or add collaborators.

---

## List Pages

Get all pages you can access.

|              |                   |
| ------------ | ----------------- |
| **Endpoint** | `GET /api/pages/` |
| **Auth**     | Bearer token      |

**Query Parameters:**

| Param    | Default | Description              |
| -------- | ------- | ------------------------ |
| `limit`  | 100     | Items per page (max 100) |
| `offset` | 0       | Items to skip            |

**Response (200):**

```json
{
  "items": [
    {
      "external_id": "abc123",
      "title": "My Page",
      "project_id": "proj123",
      "details": { "content": "..." },
      "updated": "2025-01-15T10:30:00Z",
      "created": "2025-01-10T08:00:00Z",
      "modified": "2025-01-15T10:30:00Z",
      "is_owner": true
    }
  ],
  "count": 10
}
```

---

## Autocomplete

Search pages by title for typeahead functionality.

|              |                                |
| ------------ | ------------------------------ |
| **Endpoint** | `GET /api/pages/autocomplete/` |
| **Auth**     | Bearer token                   |

**Query:** `?q=search+term`

**Response (200):**

```json
{
  "pages": [
    {
      "external_id": "abc123",
      "title": "Python Tutorial",
      "updated": "..."
    }
  ]
}
```

---

## Create Page

|              |                    |
| ------------ | ------------------ |
| **Endpoint** | `POST /api/pages/` |
| **Auth**     | Bearer token       |

| Field        | Type   | Required? | Description               |
| ------------ | ------ | --------- | ------------------------- |
| `project_id` | string | Yes       | Project to create page in |
| `title`      | string | No        | Page title                |
| `details`    | object | No        | Content and metadata      |

**Response (201):**

```json
{
  "external_id": "xyz789",
  "title": "My New Page",
  "project_id": "proj123",
  "details": {},
  "updated": "2025-01-15T14:30:00Z",
  "created": "2025-01-15T14:30:00Z",
  "modified": "2025-01-15T14:30:00Z",
  "is_owner": true
}
```

---

## Get Page

|              |                                 |
| ------------ | ------------------------------- |
| **Endpoint** | `GET /api/pages/{external_id}/` |
| **Auth**     | Bearer token                    |

**Response (200):**

```json
{
  "external_id": "abc123",
  "title": "My Page",
  "project_id": "proj123",
  "details": { "content": "Page content..." },
  "updated": "2025-01-15T10:30:00Z",
  "created": "2025-01-10T08:00:00Z",
  "modified": "2025-01-15T10:30:00Z",
  "is_owner": true
}
```

---

## Update Page

|              |                                 |
| ------------ | ------------------------------- |
| **Endpoint** | `PUT /api/pages/{external_id}/` |
| **Auth**     | Bearer token                    |

| Field     | Type   | Required? | Description          |
| --------- | ------ | --------- | -------------------- |
| `title`   | string | No        | Page title           |
| `details` | object | No        | Content and metadata |

**Response (200):**

```json
{
  "external_id": "abc123",
  "title": "Updated Title",
  "project_id": "proj123",
  "details": { "content": "New content..." },
  "updated": "2025-01-16T09:00:00Z",
  "created": "2025-01-10T08:00:00Z",
  "modified": "2025-01-16T09:00:00Z",
  "is_owner": true
}
```

---

## Delete Page

|              |                                    |
| ------------ | ---------------------------------- |
| **Endpoint** | `DELETE /api/pages/{external_id}/` |
| **Auth**     | Bearer token (owner only)          |

**Response (204):** No content.

> Soft delete—page is hidden but not permanently removed.

---

## Get Page Links

Get outgoing and incoming (backlinks) internal links for a page.

|              |                                       |
| ------------ | ------------------------------------- |
| **Endpoint** | `GET /api/pages/{external_id}/links/` |
| **Auth**     | Bearer token                          |

**Response (200):**

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

| Field       | Description                              |
| ----------- | ---------------------------------------- |
| `outgoing`  | Pages this page links to                 |
| `incoming`  | Pages that link to this page (backlinks) |
| `link_text` | Display text from the markdown link      |

> Links use format `[Link Text](/pages/{external_id}/)` and are parsed on save.

---

## Sharing

### List Editors

|              |                                         |
| ------------ | --------------------------------------- |
| **Endpoint** | `GET /api/pages/{external_id}/editors/` |
| **Auth**     | Bearer token                            |

**Response (200):**

```json
[
  {
    "external_id": "user123",
    "email": "editor@example.com",
    "role": "editor",
    "is_pending": false
  },
  {
    "external_id": "inv456",
    "email": "pending@example.com",
    "role": "viewer",
    "is_pending": true
  }
]
```

| Field        | Description                                    |
| ------------ | ---------------------------------------------- |
| `role`       | `editor` (can edit) or `viewer` (read-only)    |
| `is_pending` | `true` if invitation sent but not yet accepted |

### Add Editor

|              |                                          |
| ------------ | ---------------------------------------- |
| **Endpoint** | `POST /api/pages/{external_id}/editors/` |
| **Auth**     | Bearer token                             |

| Field   | Type   | Required? | Description                            |
| ------- | ------ | --------- | -------------------------------------- |
| `email` | string | Yes       | Email address to invite                |
| `role`  | string | No        | `editor` or `viewer` (default: viewer) |

**Response (201):**

```json
{
  "external_id": "user789",
  "email": "editor@example.com",
  "role": "viewer",
  "is_pending": true
}
```

> **Rate Limiting:** External invitations (non-org members) are limited to 10/hour. Returns `429` if exceeded.

### Update Editor Role

|              |                                                     |
| ------------ | --------------------------------------------------- |
| **Endpoint** | `PATCH /api/pages/{external_id}/editors/{user_id}/` |
| **Auth**     | Bearer token                                        |

| Field  | Type   | Required? | Description          |
| ------ | ------ | --------- | -------------------- |
| `role` | string | Yes       | `editor` or `viewer` |

**Response (200):**

```json
{
  "external_id": "user789",
  "email": "editor@example.com",
  "role": "editor",
  "is_pending": false
}
```

### Remove Editor

|              |                                                      |
| ------------ | ---------------------------------------------------- |
| **Endpoint** | `DELETE /api/pages/{external_id}/editors/{user_id}/` |
| **Auth**     | Bearer token                                         |

**Response (204):** No content.

### Validate Invitation

|              |                                                        |
| ------------ | ------------------------------------------------------ |
| **Endpoint** | `GET /api/pages/invitations/{invitation_id}/validate/` |

**Response (200):**

```json
{
  "is_valid": true,
  "page": {
    "external_id": "abc123",
    "title": "Shared Page"
  },
  "inviter": {
    "email": "owner@example.com"
  }
}
```

---

## Notes

- Pages use CRDT for real-time collaborative editing
- `updated` is managed by the collaboration system
- `modified` updates when you change title/details via REST

---

## Examples

### List your pages

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/pages/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/pages/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/pages/`, {
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

uri = URI("#{BASE_URL}/api/pages/")
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

$ch = curl_init("$baseUrl/api/pages/");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/pages/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Create a page

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl -X POST "$BASE_URL/api/pages/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "project_id": "proj123",
  "title": "My New Page"
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PROJECT_ID = "proj123"

response = requests.post(
    f"{BASE_URL}/api/pages/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"project_id": PROJECT_ID, "title": "My New Page"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PROJECT_ID = "proj123";

const response = await fetch(`${BASE_URL}/api/pages/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    project_id: PROJECT_ID,
    title: "My New Page",
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
PROJECT_ID = "proj123"

uri = URI("#{BASE_URL}/api/pages/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = { project_id: PROJECT_ID, title: "My New Page" }.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$projectId = "proj123";

$ch = curl_init("$baseUrl/api/pages/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "project_id" => $projectId,
        "title" => "My New Page"
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
    baseURL   = "BASE_URL"
    token     = "ACCESS_TOKEN"
    projectID = "proj123"
)

func main() {
    body, _ := json.Marshal(map[string]string{
        "project_id": projectID,
        "title":      "My New Page",
    })

    req, _ := http.NewRequest("POST", baseURL+"/api/pages/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Get a specific page

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"

curl "$BASE_URL/api/pages/$PAGE_ID/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_ID = "abc123"

response = requests.get(
    f"{BASE_URL}/api/pages/{PAGE_ID}/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_ID = "abc123";

const response = await fetch(`${BASE_URL}/api/pages/${PAGE_ID}/`, {
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
PAGE_ID = "abc123"

uri = URI("#{BASE_URL}/api/pages/#{PAGE_ID}/")
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
$pageId = "abc123";

$ch = curl_init("$baseUrl/api/pages/$pageId/");
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
    pageID  = "abc123"
)

func main() {
    req, _ := http.NewRequest("GET", baseURL+"/api/pages/"+pageID+"/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Update a page

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"

curl -X PUT "$BASE_URL/api/pages/$PAGE_ID/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title", "details": {"content": "New content..."}}'
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_ID = "abc123"

response = requests.put(
    f"{BASE_URL}/api/pages/{PAGE_ID}/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"title": "Updated Title", "details": {"content": "New content..."}}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_ID = "abc123";

const response = await fetch(`${BASE_URL}/api/pages/${PAGE_ID}/`, {
  method: "PUT",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    title: "Updated Title",
    details: { content: "New content..." },
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
PAGE_ID = "abc123"

uri = URI("#{BASE_URL}/api/pages/#{PAGE_ID}/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Put.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = {
  title: "Updated Title",
  details: { content: "New content..." }
}.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$pageId = "abc123";

$ch = curl_init("$baseUrl/api/pages/$pageId/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_CUSTOMREQUEST => "PUT",
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "title" => "Updated Title",
        "details" => ["content" => "New content..."]
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
    pageID  = "abc123"
)

func main() {
    body, _ := json.Marshal(map[string]interface{}{
        "title":   "Updated Title",
        "details": map[string]string{"content": "New content..."},
    })

    req, _ := http.NewRequest("PUT", baseURL+"/api/pages/"+pageID+"/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Get page links (backlinks)

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"

curl "$BASE_URL/api/pages/$PAGE_ID/links/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_ID = "abc123"

response = requests.get(
    f"{BASE_URL}/api/pages/{PAGE_ID}/links/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_ID = "abc123";

const response = await fetch(`${BASE_URL}/api/pages/${PAGE_ID}/links/`, {
  headers: { Authorization: `Bearer ${TOKEN}` },
});
console.log(await response.json());
```

### Search pages

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/pages/autocomplete/?q=python" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/pages/autocomplete/",
    params={"q": "python"},
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/pages/autocomplete/?q=python`, {
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

uri = URI("#{BASE_URL}/api/pages/autocomplete/")
uri.query = URI.encode_www_form(q: "python")
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

$ch = curl_init("$baseUrl/api/pages/autocomplete/?q=python");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/pages/autocomplete/?q=python", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```
