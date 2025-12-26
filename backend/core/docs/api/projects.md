# Projects

Projects are containers for pages within an organization. Access is granted through org membership or project-level sharing.

## Access Control

| Tier    | Description                          |
| ------- | ------------------------------------ |
| Org     | Member of the project's organization |
| Project | Added as a project editor            |

Access is granted if **either** tier applies.

---

## List Projects

|              |                      |
| ------------ | -------------------- |
| **Endpoint** | `GET /api/projects/` |
| **Auth**     | Bearer token         |

**Query Parameters:**

| Param     | Description                    |
| --------- | ------------------------------ |
| `org_id`  | Filter by organization         |
| `details` | Set to `full` to include pages |

**Response (200):**

```json
[
  {
    "external_id": "abc123",
    "name": "My Project",
    "description": "...",
    "modified": "2025-01-15T10:30:00Z",
    "created": "2025-01-10T08:00:00Z",
    "creator": {
      "external_id": "user123",
      "email": "..."
    },
    "org": {
      "external_id": "org123",
      "name": "..."
    },
    "pages": null
  }
]
```

With `?details=full`, `pages` contains an array of page objects.

---

## Get Project

|              |                                    |
| ------------ | ---------------------------------- |
| **Endpoint** | `GET /api/projects/{external_id}/` |
| **Auth**     | Bearer token                       |

**Query:** `?details=full` to include pages.

**Response (200):**

```json
{
  "external_id": "abc123",
  "name": "My Project",
  "description": "Project description",
  "modified": "2025-01-15T10:30:00Z",
  "created": "2025-01-10T08:00:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization"
  },
  "pages": null
}
```

---

## Create Project

|              |                           |
| ------------ | ------------------------- |
| **Endpoint** | `POST /api/projects/`     |
| **Auth**     | Bearer token (org member) |

| Field         | Type   | Required? | Description     |
| ------------- | ------ | --------- | --------------- |
| `org_id`      | string | Yes       | Organization ID |
| `name`        | string | Yes       | Project name    |
| `description` | string | No        | Description     |

**Response (201):**

```json
{
  "external_id": "xyz789",
  "name": "New Project",
  "description": "Project description",
  "modified": "2025-01-15T14:30:00Z",
  "created": "2025-01-15T14:30:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization"
  },
  "pages": null
}
```

---

## Update Project

|              |                                      |
| ------------ | ------------------------------------ |
| **Endpoint** | `PATCH /api/projects/{external_id}/` |
| **Auth**     | Bearer token                         |

| Field         | Type   | Required? | Description  |
| ------------- | ------ | --------- | ------------ |
| `name`        | string | No        | Project name |
| `description` | string | No        | Description  |

**Response (200):**

```json
{
  "external_id": "abc123",
  "name": "Updated Project Name",
  "description": "Updated description",
  "modified": "2025-01-16T09:00:00Z",
  "created": "2025-01-10T08:00:00Z",
  "creator": {
    "external_id": "user123",
    "email": "creator@example.com"
  },
  "org": {
    "external_id": "org123",
    "name": "My Organization"
  },
  "pages": null
}
```

---

## Delete Project

|              |                                       |
| ------------ | ------------------------------------- |
| **Endpoint** | `DELETE /api/projects/{external_id}/` |
| **Auth**     | Bearer token (creator only)           |

**Response (204):** No content.

> Soft delete—project is hidden but not permanently removed.

---

## Sharing

### List Editors

|              |                                            |
| ------------ | ------------------------------------------ |
| **Endpoint** | `GET /api/projects/{external_id}/editors/` |
| **Auth**     | Bearer token                               |

**Response (200):**

```json
[
  {
    "external_id": "user123",
    "email": "...",
    "is_creator": false,
    "is_pending": false
  },
  {
    "external_id": "inv456",
    "email": "...",
    "is_creator": false,
    "is_pending": true
  }
]
```

### Add Editor

|              |                                             |
| ------------ | ------------------------------------------- |
| **Endpoint** | `POST /api/projects/{external_id}/editors/` |
| **Auth**     | Bearer token                                |

| Field   | Type   | Required? | Description             |
| ------- | ------ | --------- | ----------------------- |
| `email` | string | Yes       | Email address to invite |

**Response (201):**

```json
{
  "external_id": "user789",
  "email": "collaborator@example.com",
  "is_creator": false,
  "is_pending": false
}
```

- Existing users are added immediately
- New users receive an email invitation

### Remove Editor

|              |                                                         |
| ------------ | ------------------------------------------------------- |
| **Endpoint** | `DELETE /api/projects/{external_id}/editors/{user_id}/` |
| **Auth**     | Bearer token                                            |

**Response (204):** No content.

> Cannot remove the project creator.

### Validate Invitation

|              |                                                  |
| ------------ | ------------------------------------------------ |
| **Endpoint** | `GET /api/projects/invitations/{token}/validate` |
| **Auth**     | None required                                    |

**Response (200):**

```json
{
  "action": "redirect",
  "redirect_to": "/projects/proj123",
  "email": "invited@example.com",
  "project_name": "My Project"
}
```

For unauthenticated users, `action` is `"signup"` to indicate they should create an account.

---

## Examples

### List all projects

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/projects/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/projects/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/projects/`, {
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

uri = URI("#{BASE_URL}/api/projects/")
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

$ch = curl_init("$baseUrl/api/projects/");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/projects/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result []map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### List projects with pages

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/projects/?details=full" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/projects/",
    params={"details": "full"},
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/projects/?details=full`, {
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

uri = URI("#{BASE_URL}/api/projects/")
uri.query = URI.encode_www_form(details: "full")
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

$ch = curl_init("$baseUrl/api/projects/?details=full");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/projects/?details=full", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result []map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Create a project

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl -X POST "$BASE_URL/api/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "org_id": "org123",
  "name": "New Project",
  "description": "Project description"
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
ORG_ID = "org123"

response = requests.post(
    f"{BASE_URL}/api/projects/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "org_id": ORG_ID,
        "name": "New Project",
        "description": "Project description"
    }
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const ORG_ID = "org123";

const response = await fetch(`${BASE_URL}/api/projects/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    org_id: ORG_ID,
    name: "New Project",
    description: "Project description",
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

uri = URI("#{BASE_URL}/api/projects/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = {
  org_id: ORG_ID,
  name: "New Project",
  description: "Project description"
}.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$orgId = "org123";

$ch = curl_init("$baseUrl/api/projects/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "org_id" => $orgId,
        "name" => "New Project",
        "description" => "Project description"
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
        "org_id":      orgID,
        "name":        "New Project",
        "description": "Project description",
    })

    req, _ := http.NewRequest("POST", baseURL+"/api/projects/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Share a project

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PROJECT_ID="abc123"

curl -X POST "$BASE_URL/api/projects/$PROJECT_ID/editors/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "email": "collaborator@example.com"
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PROJECT_ID = "abc123"

response = requests.post(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/editors/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"email": "collaborator@example.com"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PROJECT_ID = "abc123";

const response = await fetch(`${BASE_URL}/api/projects/${PROJECT_ID}/editors/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ email: "collaborator@example.com" }),
});
console.log(await response.json());
```

```ruby
require 'net/http'
require 'json'
require 'uri'

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PROJECT_ID = "abc123"

uri = URI("#{BASE_URL}/api/projects/#{PROJECT_ID}/editors/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = { email: "collaborator@example.com" }.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$projectId = "abc123";

$ch = curl_init("$baseUrl/api/projects/$projectId/editors/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode(["email" => "collaborator@example.com"])
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
    projectID = "abc123"
)

func main() {
    body, _ := json.Marshal(map[string]string{"email": "collaborator@example.com"})

    req, _ := http.NewRequest("POST", baseURL+"/api/projects/"+projectID+"/editors/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```
