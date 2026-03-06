# Rewind

Rewind provides an automatic history of page content over time. Every time a page is edited through real-time collaboration, a rewind point is created capturing the content at that point. You can list rewinds, view their full content, restore a page to a previous rewind, or add labels for easy reference.

---

## List Rewinds

Get all rewinds for a page, ordered by most recent first. Content is excluded from the list response for performance—use the detail endpoint to retrieve full content.

|              |                                       |
| ------------ | ------------------------------------- |
| **Endpoint** | `GET /api/v1/pages/{page_id}/rewind/` |
| **Auth**     | Bearer token                          |

**Query Parameters:**

| Param    | Default | Description                                |
| -------- | ------- | ------------------------------------------ |
| `limit`  | 100     | Items per page (max 100)                   |
| `offset` | 0       | Items to skip                              |
| `label`  |         | Filter by label (case-insensitive partial) |

**Response (200):**

```json
{
  "items": [
    {
      "external_id": "ver_abc123",
      "rewind_number": 42,
      "title": "My Page",
      "content_size_bytes": 2048,
      "editors": ["user_ext1", "user_ext2"],
      "label": "Before refactor",
      "is_compacted": false,
      "compacted_from_count": 0,
      "created": "2025-01-15T10:30:00Z"
    }
  ],
  "count": 42
}
```

| Field                  | Description                                                 |
| ---------------------- | ----------------------------------------------------------- |
| `external_id`          | Unique rewind identifier                                    |
| `rewind_number`        | Sequential rewind number within the page                    |
| `title`                | Page title at the time of this rewind                       |
| `content_size_bytes`   | Size of the content in bytes                                |
| `editors`              | User external IDs of editors active during this rewind      |
| `label`                | User-set label (empty string if none)                       |
| `is_compacted`         | Whether this rewind was created by compaction               |
| `compacted_from_count` | Number of rewinds merged into this one (0 if not compacted) |
| `created`              | When this rewind was created                                |

---

## Get Rewind

Retrieve a single rewind with its full content.

|              |                                                   |
| ------------ | ------------------------------------------------- |
| **Endpoint** | `GET /api/v1/pages/{page_id}/rewind/{rewind_id}/` |
| **Auth**     | Bearer token                                      |

**Response (200):**

```json
{
  "external_id": "ver_abc123",
  "rewind_number": 42,
  "title": "My Page",
  "content": "Full page content at this rewind...",
  "content_size_bytes": 2048,
  "editors": ["user_ext1", "user_ext2"],
  "label": "Before refactor",
  "is_compacted": false,
  "compacted_from_count": 0,
  "created": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**

- **403** - User doesn't have access to the page
- **404** - Page or rewind not found

---

## Restore Rewind

Restore a page to a previous rewind. This creates a new rewind recording the restore, updates the page content and title, resets the collaborative editing state, and disconnects all active WebSocket clients so they reload with the restored content.

|              |                                                            |
| ------------ | ---------------------------------------------------------- |
| **Endpoint** | `POST /api/v1/pages/{page_id}/rewind/{rewind_id}/restore/` |
| **Auth**     | Bearer token (editor role required)                        |

**Response (200):**

```json
{
  "external_id": "ver_new789",
  "rewind_number": 43,
  "title": "My Page",
  "content": "Full page content restored from rewind 42...",
  "content_size_bytes": 2048,
  "editors": ["user_ext1"],
  "label": "Restored from v42",
  "is_compacted": false,
  "compacted_from_count": 0,
  "created": "2025-01-16T09:00:00Z"
}
```

> The response is the newly created restore rewind, not the original rewind that was restored from.

**Error Responses:**

- **403** - User doesn't have write permission (viewer role or no editor access)
- **404** - Page or rewind not found

---

## Update Rewind Label

Set or change a rewind's label. Labels help you mark important rewinds for easy reference. Pass an empty string to remove a label.

|              |                                                     |
| ------------ | --------------------------------------------------- |
| **Endpoint** | `PATCH /api/v1/pages/{page_id}/rewind/{rewind_id}/` |
| **Auth**     | Bearer token (editor role required)                 |

| Field   | Type   | Required? | Description                  |
| ------- | ------ | --------- | ---------------------------- |
| `label` | string | Yes       | Rewind label (max 255 chars) |

**Response (200):**

```json
{
  "external_id": "ver_abc123",
  "rewind_number": 42,
  "title": "My Page",
  "content": "Full page content...",
  "content_size_bytes": 2048,
  "editors": ["user_ext1", "user_ext2"],
  "label": "Before refactor",
  "is_compacted": false,
  "compacted_from_count": 0,
  "created": "2025-01-15T10:30:00Z"
}
```

**Error Responses:**

- **403** - User doesn't have write permission (viewer role or no editor access)
- **404** - Page or rewind not found

---

## Notes

- Rewinds are auto-created by the collaboration system—you don't need to create them manually
- The `editors` list contains user external IDs of users who were editing when the rewind was saved
- `is_compacted` and `compacted_from_count` are system fields from automatic storage optimization; older rewinds may be compacted into hourly snapshots
- Labeled rewinds are never automatically compacted
- Restoring a rewind resets the real-time collaboration state (CRDT), so all connected editors will need to reconnect

---

## Examples

### List rewinds

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"

curl "$BASE_URL/api/v1/pages/$PAGE_ID/rewind/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_ID = "abc123"

response = requests.get(
    f"{BASE_URL}/api/v1/pages/{PAGE_ID}/rewind/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_ID = "abc123";

const response = await fetch(`${BASE_URL}/api/v1/pages/${PAGE_ID}/rewind/`, {
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

uri = URI("#{BASE_URL}/api/v1/pages/#{PAGE_ID}/rewind/")
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

$ch = curl_init("$baseUrl/api/v1/pages/$pageId/rewind/");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/v1/pages/"+pageID+"/rewind/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Get a rewind

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"
REWIND_ID="ver_abc123"

curl "$BASE_URL/api/v1/pages/$PAGE_ID/rewind/$REWIND_ID/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_ID = "abc123"
REWIND_ID = "ver_abc123"

response = requests.get(
    f"{BASE_URL}/api/v1/pages/{PAGE_ID}/rewind/{REWIND_ID}/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_ID = "abc123";
const REWIND_ID = "ver_abc123";

const response = await fetch(`${BASE_URL}/api/v1/pages/${PAGE_ID}/rewind/${REWIND_ID}/`, {
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
REWIND_ID = "ver_abc123"

uri = URI("#{BASE_URL}/api/v1/pages/#{PAGE_ID}/rewind/#{REWIND_ID}/")
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
$rewindId = "ver_abc123";

$ch = curl_init("$baseUrl/api/v1/pages/$pageId/rewind/$rewindId/");
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
    baseURL   = "<BASE_URL>"
    token     = "<ACCESS_TOKEN>"
    pageID    = "abc123"
    rewindID = "ver_abc123"
)

func main() {
    url := baseURL + "/api/v1/pages/" + pageID + "/rewind/" + rewindID + "/"
    req, _ := http.NewRequest("GET", url, nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Restore a rewind

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"
PAGE_ID="abc123"
REWIND_ID="ver_abc123"

curl -X POST "$BASE_URL/api/v1/pages/$PAGE_ID/rewind/$REWIND_ID/restore/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_ID = "abc123"
REWIND_ID = "ver_abc123"

response = requests.post(
    f"{BASE_URL}/api/v1/pages/{PAGE_ID}/rewind/{REWIND_ID}/restore/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_ID = "abc123";
const REWIND_ID = "ver_abc123";

const response = await fetch(`${BASE_URL}/api/v1/pages/${PAGE_ID}/rewind/${REWIND_ID}/restore/`, {
  method: "POST",
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
REWIND_ID = "ver_abc123"

uri = URI("#{BASE_URL}/api/v1/pages/#{PAGE_ID}/rewind/#{REWIND_ID}/restore/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$pageId = "abc123";
$rewindId = "ver_abc123";

$ch = curl_init("$baseUrl/api/v1/pages/$pageId/rewind/$rewindId/restore/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
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
    baseURL   = "<BASE_URL>"
    token     = "<ACCESS_TOKEN>"
    pageID    = "abc123"
    rewindID = "ver_abc123"
)

func main() {
    url := baseURL + "/api/v1/pages/" + pageID + "/rewind/" + rewindID + "/restore/"
    req, _ := http.NewRequest("POST", url, nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```
