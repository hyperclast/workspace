# Ask

AI-powered question answering about your pages using RAG (Retrieval-Augmented Generation).

## Ask a Question

Submit a question and receive an AI-generated answer based on relevant page content.

|              |                  |
| ------------ | ---------------- |
| **Endpoint** | `POST /api/ask/` |
| **Auth**     | Bearer token     |

### Request Body

| Field      | Type     | Required? | Description                             |
| ---------- | -------- | --------- | --------------------------------------- |
| `query`    | string   | Yes       | The question to ask (1-10,000 chars)    |
| `page_ids` | string[] | No        | Specific page IDs to include in context |

**Sample Request**

```json
{
  "query": "What are my meeting pages about?",
  "page_ids": ["abc123", "def456"]
}
```

### Response

**Response (200):**

```json
{
  "answer": "Your meeting pages cover the Q4 planning session...",
  "pages": [
    {
      "external_id": "abc123",
      "title": "Q4 Planning Meeting",
      "updated": "2025-01-15T10:30:00Z",
      "created": "2025-01-10T08:00:00Z",
      "modified": "2025-01-15T10:30:00Z"
    }
  ]
}
```

### Error Responses

| Code | Error                  | Description                                |
| ---- | ---------------------- | ------------------------------------------ |
| 400  | `empty_question`       | Query is blank or contains only whitespace |
| 400  | `no_matching_pages`    | No pages match the query                   |
| 400  | `api_error`            | LLM API error (rate limits, unavailable)   |
| 400  | `unexpected`           | Unexpected processing error                |
| 422  | Validation error       | Invalid request body                       |
| 429  | Too Many Requests      | Rate limit exceeded (default: 30 req/min)  |
| 503  | `ask_feature_disabled` | Feature temporarily unavailable            |

---

## Examples

### Basic Query

Uses vector similarity to find relevant pages automatically:

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl -X POST "$BASE_URL/api/ask/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "query": "What did we discuss in yesterday's meeting?"
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.post(
    f"{BASE_URL}/api/ask/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"query": "What did we discuss in yesterday's meeting?"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/ask/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    query: "What did we discuss in yesterday's meeting?",
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

uri = URI("#{BASE_URL}/api/ask/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = { query: "What did we discuss in yesterday's meeting?" }.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";

$ch = curl_init("$baseUrl/api/ask/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "query" => "What did we discuss in yesterday's meeting?"
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
)

func main() {
    body, _ := json.Marshal(map[string]string{
        "query": "What did we discuss in yesterday's meeting?",
    })

    req, _ := http.NewRequest("POST", baseURL+"/api/ask/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Query with Specific Pages

Only uses the specified pages for context:

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl -X POST "$BASE_URL/api/ask/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "query": "Summarize the key points",
  "page_ids": ["abc123", "def456"]
}
EOF
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"
PAGE_IDS = ["abc123", "def456"]

response = requests.post(
    f"{BASE_URL}/api/ask/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "query": "Summarize the key points",
        "page_ids": PAGE_IDS
    }
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";
const PAGE_IDS = ["abc123", "def456"];

const response = await fetch(`${BASE_URL}/api/ask/`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    query: "Summarize the key points",
    page_ids: PAGE_IDS,
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
PAGE_IDS = ["abc123", "def456"]

uri = URI("#{BASE_URL}/api/ask/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = {
  query: "Summarize the key points",
  page_ids: PAGE_IDS
}.to_json

response = http.request(request)
puts JSON.parse(response.body)
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";
$pageIds = ["abc123", "def456"];

$ch = curl_init("$baseUrl/api/ask/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "query" => "Summarize the key points",
        "page_ids" => $pageIds
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
)

var pageIDs = []string{"abc123", "def456"}

func main() {
    body, _ := json.Marshal(map[string]interface{}{
        "query":    "Summarize the key points",
        "page_ids": pageIDs,
    })

    req, _ := http.NewRequest("POST", baseURL+"/api/ask/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```
