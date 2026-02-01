# Users

Manage user information and API access tokens.

## Get Current User

Returns the authenticated user's profile and access token.

|              |                      |
| ------------ | -------------------- |
| **Endpoint** | `GET /api/users/me/` |
| **Auth**     | Bearer token         |

**Response (200):**

```json
{
  "external_id": "abc123",
  "email": "user@example.com",
  "email_verified": true,
  "username": "user",
  "first_name": "John",
  "last_name": "Doe",
  "is_authenticated": true,
  "access_token": "NhqPaZgfmRLxcBvYS..."
}
```

**Error (401):** Not authenticated

---

## Get Access Token

Returns only the access token. Useful for retrieving your token from the web app.

|              |                            |
| ------------ | -------------------------- |
| **Endpoint** | `GET /api/users/me/token/` |
| **Auth**     | Bearer token or session    |

**Response (200):**

```json
{
  "access_token": "NhqPaZgfmRLxcBvYS..."
}
```

---

## Regenerate Access Token

Generate a new token, immediately invalidating the old one.

|              |                                        |
| ------------ | -------------------------------------- |
| **Endpoint** | `POST /api/users/me/token/regenerate/` |
| **Auth**     | Bearer token or session                |

**Response (200):**

```json
{
  "access_token": "dGhpcyBpcyBhIG5ldyB0b2tlbg..."
}
```

> **Warning:** The old token is immediately invalidated. Update all appls that are using the old token.

---

## Get Storage Summary

Get the total storage used by the current user.

|              |                           |
| ------------ | ------------------------- |
| **Endpoint** | `GET /api/users/storage/` |
| **Auth**     | Bearer token              |

**Response (200):**

```json
{
  "total_bytes": 15728640,
  "file_count": 12
}
```

| Field         | Description                    |
| ------------- | ------------------------------ |
| `total_bytes` | Sum of all file sizes in bytes |
| `file_count`  | Total number of files uploaded |

> **Note:** Only counts files that have completed uploading (status: `available`).

---

## Examples

### Get user info

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/users/me/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/users/me/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/users/me/`, {
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

uri = URI("#{BASE_URL}/api/users/me/")
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

$ch = curl_init("$baseUrl/api/users/me/");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/users/me/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Get access token

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/users/me/token/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/users/me/token/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
print(response.json())
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/users/me/token/`, {
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

uri = URI("#{BASE_URL}/api/users/me/token/")
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

$ch = curl_init("$baseUrl/api/users/me/token/");
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
    req, _ := http.NewRequest("GET", baseURL+"/api/users/me/token/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}
```

### Regenerate token

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl -X POST "$BASE_URL/api/users/me/token/regenerate/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.post(
    f"{BASE_URL}/api/users/me/token/regenerate/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
new_token = response.json()["access_token"]
print(f"New token: {new_token}")
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/users/me/token/regenerate/`, {
  method: "POST",
  headers: { Authorization: `Bearer ${TOKEN}` },
});
const { access_token } = await response.json();
console.log("New token:", access_token);
```

```ruby
require 'net/http'
require 'json'
require 'uri'

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

uri = URI("#{BASE_URL}/api/users/me/token/regenerate/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"

response = http.request(request)
result = JSON.parse(response.body)
puts "New token: #{result['access_token']}"
```

```php
<?php
$baseUrl = "<BASE_URL>";
$token = "<ACCESS_TOKEN>";

$ch = curl_init("$baseUrl/api/users/me/token/regenerate/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => ["Authorization: Bearer $token"]
]);
$response = curl_exec($ch);
curl_close($ch);
$result = json_decode($response, true);
echo "New token: " . $result["access_token"];
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
    req, _ := http.NewRequest("POST", baseURL+"/api/users/me/token/regenerate/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := http.DefaultClient.Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println("New token:", result["access_token"])
}
```

### Get storage summary

```bash
BASE_URL="<BASE_URL>"
TOKEN="<ACCESS_TOKEN>"

curl "$BASE_URL/api/users/storage/" \
  -H "Authorization: Bearer $TOKEN"
```

```python
import requests

BASE_URL = "<BASE_URL>"
TOKEN = "<ACCESS_TOKEN>"

response = requests.get(
    f"{BASE_URL}/api/users/storage/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
data = response.json()
print(f"Files: {data['file_count']}, Size: {data['total_bytes']} bytes")
```

```javascript
const BASE_URL = "<BASE_URL>";
const TOKEN = "<ACCESS_TOKEN>";

const response = await fetch(`${BASE_URL}/api/users/storage/`, {
  headers: { Authorization: `Bearer ${TOKEN}` },
});
const { file_count, total_bytes } = await response.json();
console.log(`Files: ${file_count}, Size: ${total_bytes} bytes`);
```
