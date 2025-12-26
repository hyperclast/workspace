<script>
  import { onMount } from "svelte";
  import { getState, registerPageChangeHandler } from "../../stores/sidebar.svelte.js";
  import { showToast } from "../../toast.js";
  import { csrfFetch } from "../../../csrf.js";
  import { API_BASE_URL } from "../../../config.js";

  const LANG_STORAGE_KEY = "ws-dev-tab-lang";

  const sidebarState = getState();

  let selectedLang = $state(localStorage.getItem(LANG_STORAGE_KEY) || "curl");
  let apiToken = $state(null);
  let currentProjectId = $state(null);
  let currentPageId = $state(null);
  let loading = $state(true);
  let otherDropdownOpen = $state(false);

  const mainLanguages = [
    { id: "curl", label: "cURL" },
    { id: "python", label: "Python" },
    { id: "javascript", label: "JavaScript" },
  ];

  const otherLanguages = [
    { id: "ruby", label: "Ruby" },
    { id: "php", label: "PHP" },
    { id: "go", label: "Go" },
  ];

  const allLanguages = [...mainLanguages, ...otherLanguages];

  function selectLanguage(lang) {
    selectedLang = lang;
    localStorage.setItem(LANG_STORAGE_KEY, lang);
    otherDropdownOpen = false;
  }

  function toggleOtherDropdown(e) {
    e.stopPropagation();
    otherDropdownOpen = !otherDropdownOpen;
  }

  function closeOtherDropdown() {
    otherDropdownOpen = false;
  }

  function isOtherLanguage(lang) {
    return otherLanguages.some(l => l.id === lang);
  }

  function getSelectedOtherLabel() {
    const lang = otherLanguages.find(l => l.id === selectedLang);
    return lang ? lang.label : "Other";
  }

  async function fetchApiToken() {
    try {
      const response = await csrfFetch(`${API_BASE_URL}/api/users/me/`);
      if (response.ok) {
        const data = await response.json();
        apiToken = data.access_token;
      }
    } catch (error) {
      console.error("Failed to fetch API token:", error);
    } finally {
      loading = false;
    }
  }

  function findProjectForPage(pageId) {
    if (window._currentProjectId) return window._currentProjectId;
    const cachedProjects = window._cachedProjects || [];
    for (const project of cachedProjects) {
      if (project.pages?.some((p) => p.external_id === pageId)) {
        return project.external_id;
      }
    }
    return null;
  }

  function getBaseUrl() {
    return `${window.location.protocol}//${window.location.host}`;
  }

  function generateCreatePageCode(lang, projectId, token) {
    const baseUrl = getBaseUrl();
    const projectIdStr = projectId || "YOUR_PROJECT_ID";
    const tokenStr = token || "YOUR_API_TOKEN";

    if (lang === "curl") {
      return `BASE_URL="${baseUrl}"
TOKEN="${tokenStr}"

curl -X POST "$BASE_URL/api/pages/" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d @- <<EOF
{
  "project_id": "${projectIdStr}",
  "title": "New Page",
  "details": {
    "content": "Page content here..."
  }
}
EOF`;
    }

    if (lang === "python") {
      return `import requests

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PROJECT_ID = "${projectIdStr}"

response = requests.post(
    f"{BASE_URL}/api/pages/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "project_id": PROJECT_ID,
        "title": "New Page",
        "details": {"content": "Page content here..."}
    }
)
print(response.json())`;
    }

    if (lang === "javascript") {
      return `const BASE_URL = "${baseUrl}";
const TOKEN = "${tokenStr}";
const PROJECT_ID = "${projectIdStr}";

const response = await fetch(\`\${BASE_URL}/api/pages/\`, {
  method: "POST",
  headers: {
    "Authorization": \`Bearer \${TOKEN}\`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    project_id: PROJECT_ID,
    title: "New Page",
    details: { content: "Page content here..." }
  })
});
console.log(await response.json());`;
    }

    if (lang === "ruby") {
      return `require 'net/http'
require 'json'
require 'uri'

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PROJECT_ID = "${projectIdStr}"

uri = URI("#{BASE_URL}/api/pages/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Post.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"
request["Content-Type"] = "application/json"
request.body = {
  project_id: PROJECT_ID,
  title: "New Page",
  details: { content: "Page content here..." }
}.to_json

response = http.request(request)
puts JSON.parse(response.body)`;
    }

    if (lang === "php") {
      return `<?php
$baseUrl = "${baseUrl}";
$token = "${tokenStr}";
$projectId = "${projectIdStr}";

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
        "title" => "New Page",
        "details" => ["content" => "Page content here..."]
    ])
]);

$response = curl_exec($ch);
curl_close($ch);
print_r(json_decode($response, true));`;
    }

    if (lang === "go") {
      return `package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL   = "${baseUrl}"
    token     = "${tokenStr}"
    projectID = "${projectIdStr}"
)

func main() {
    payload := map[string]interface{}{
        "project_id": projectID,
        "title":      "New Page",
        "details":    map[string]string{"content": "Page content here..."},
    }
    body, _ := json.Marshal(payload)

    req, _ := http.NewRequest("POST", baseURL+"/api/pages/", bytes.NewBuffer(body))
    req.Header.Set("Authorization", "Bearer "+token)
    req.Header.Set("Content-Type", "application/json")

    resp, _ := (&http.Client{}).Do(req)
    defer resp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&result)
    fmt.Println(result)
}`;
    }
  }

  function generateListPagesCode(lang, projectId, token) {
    const baseUrl = getBaseUrl();
    const projectIdStr = projectId || "YOUR_PROJECT_ID";
    const tokenStr = token || "YOUR_API_TOKEN";

    if (lang === "curl") {
      return `BASE_URL="${baseUrl}"
TOKEN="${tokenStr}"
PROJECT_ID="${projectIdStr}"

curl "$BASE_URL/api/projects/$PROJECT_ID/?details=full" \\
  -H "Authorization: Bearer $TOKEN"`;
    }

    if (lang === "python") {
      return `import requests

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PROJECT_ID = "${projectIdStr}"

response = requests.get(
    f"{BASE_URL}/api/projects/{PROJECT_ID}/",
    params={"details": "full"},
    headers={"Authorization": f"Bearer {TOKEN}"}
)
project = response.json()
for page in project["pages"]:
    print(page["title"], page["external_id"])`;
    }

    if (lang === "javascript") {
      return `const BASE_URL = "${baseUrl}";
const TOKEN = "${tokenStr}";
const PROJECT_ID = "${projectIdStr}";

const response = await fetch(\`\${BASE_URL}/api/projects/\${PROJECT_ID}/?details=full\`, {
  headers: { "Authorization": \`Bearer \${TOKEN}\` }
});
const project = await response.json();
project.pages.forEach(page => console.log(page.title, page.external_id));`;
    }

    if (lang === "ruby") {
      return `require 'net/http'
require 'json'
require 'uri'

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PROJECT_ID = "${projectIdStr}"

uri = URI("#{BASE_URL}/api/projects/#{PROJECT_ID}/?details=full")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Get.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"

response = http.request(request)
project = JSON.parse(response.body)
project["pages"].each { |page| puts "#{page["title"]} #{page["external_id"]}" }`;
    }

    if (lang === "php") {
      return `<?php
$baseUrl = "${baseUrl}";
$token = "${tokenStr}";
$projectId = "${projectIdStr}";

$ch = curl_init("$baseUrl/api/projects/$projectId/?details=full");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => ["Authorization: Bearer $token"]
]);

$response = curl_exec($ch);
curl_close($ch);
$project = json_decode($response, true);
foreach ($project["pages"] as $page) {
    echo $page["title"] . " " . $page["external_id"] . "\\n";
}`;
    }

    if (lang === "go") {
      return `package main

import (
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL   = "${baseUrl}"
    token     = "${tokenStr}"
    projectID = "${projectIdStr}"
)

func main() {
    req, _ := http.NewRequest("GET", baseURL+"/api/projects/"+projectID+"/?details=full", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := (&http.Client{}).Do(req)
    defer resp.Body.Close()

    var project map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&project)
    for _, page := range project["pages"].([]interface{}) {
        p := page.(map[string]interface{})
        fmt.Println(p["title"], p["external_id"])
    }
}`;
    }
  }

  function generateGetPageCode(lang, pageId, token) {
    const baseUrl = getBaseUrl();
    const pageIdStr = pageId || "YOUR_PAGE_ID";
    const tokenStr = token || "YOUR_API_TOKEN";

    if (lang === "curl") {
      return `BASE_URL="${baseUrl}"
TOKEN="${tokenStr}"
PAGE_ID="${pageIdStr}"

curl "$BASE_URL/api/pages/$PAGE_ID/" \\
  -H "Authorization: Bearer $TOKEN"`;
    }

    if (lang === "python") {
      return `import requests

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PAGE_ID = "${pageIdStr}"

response = requests.get(
    f"{BASE_URL}/api/pages/{PAGE_ID}/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
page = response.json()
print(page["details"]["content"])`;
    }

    if (lang === "javascript") {
      return `const BASE_URL = "${baseUrl}";
const TOKEN = "${tokenStr}";
const PAGE_ID = "${pageIdStr}";

const response = await fetch(\`\${BASE_URL}/api/pages/\${PAGE_ID}/\`, {
  headers: { "Authorization": \`Bearer \${TOKEN}\` }
});
const page = await response.json();
console.log(page.details.content);`;
    }

    if (lang === "ruby") {
      return `require 'net/http'
require 'json'
require 'uri'

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PAGE_ID = "${pageIdStr}"

uri = URI("#{BASE_URL}/api/pages/#{PAGE_ID}/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

request = Net::HTTP::Get.new(uri)
request["Authorization"] = "Bearer #{TOKEN}"

response = http.request(request)
page = JSON.parse(response.body)
puts page["details"]["content"]`;
    }

    if (lang === "php") {
      return `<?php
$baseUrl = "${baseUrl}";
$token = "${tokenStr}";
$pageId = "${pageIdStr}";

$ch = curl_init("$baseUrl/api/pages/$pageId/");
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => ["Authorization: Bearer $token"]
]);

$response = curl_exec($ch);
curl_close($ch);
$page = json_decode($response, true);
echo $page["details"]["content"];`;
    }

    if (lang === "go") {
      return `package main

import (
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL = "${baseUrl}"
    token   = "${tokenStr}"
    pageID  = "${pageIdStr}"
)

func main() {
    req, _ := http.NewRequest("GET", baseURL+"/api/pages/"+pageID+"/", nil)
    req.Header.Set("Authorization", "Bearer "+token)

    resp, _ := (&http.Client{}).Do(req)
    defer resp.Body.Close()

    var page map[string]interface{}
    json.NewDecoder(resp.Body).Decode(&page)
    details := page["details"].(map[string]interface{})
    fmt.Println(details["content"])
}`;
    }
  }

  function generateAppendPageCode(lang, pageId, token) {
    const baseUrl = getBaseUrl();
    const pageIdStr = pageId || "YOUR_PAGE_ID";
    const tokenStr = token || "YOUR_API_TOKEN";

    if (lang === "curl") {
      return `BASE_URL="${baseUrl}"
TOKEN="${tokenStr}"
PAGE_ID="${pageIdStr}"

# Get current content
CURRENT=$(curl -s "$BASE_URL/api/pages/$PAGE_ID/" \\
  -H "Authorization: Bearer $TOKEN" | jq -r '.details.content')

# Append new content
curl -X PUT "$BASE_URL/api/pages/$PAGE_ID/" \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d @- <<EOF
{
  "details": {
    "content": "\${CURRENT}\\n\\nNew content to append"
  }
}
EOF`;
    }

    if (lang === "python") {
      return `import requests

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PAGE_ID = "${pageIdStr}"

# Get current content
response = requests.get(
    f"{BASE_URL}/api/pages/{PAGE_ID}/",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
current_content = response.json()["details"].get("content", "")

# Append new content
new_content = current_content + "\\n\\nNew content to append"
response = requests.put(
    f"{BASE_URL}/api/pages/{PAGE_ID}/",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"details": {"content": new_content}}
)
print(response.json())`;
    }

    if (lang === "javascript") {
      return `const BASE_URL = "${baseUrl}";
const TOKEN = "${tokenStr}";
const PAGE_ID = "${pageIdStr}";

// Get current content
const getResp = await fetch(\`\${BASE_URL}/api/pages/\${PAGE_ID}/\`, {
  headers: { "Authorization": \`Bearer \${TOKEN}\` }
});
const currentContent = (await getResp.json()).details?.content || "";

// Append new content
const newContent = currentContent + "\\n\\nNew content to append";
const updateResp = await fetch(\`\${BASE_URL}/api/pages/\${PAGE_ID}/\`, {
  method: "PUT",
  headers: {
    "Authorization": \`Bearer \${TOKEN}\`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({ details: { content: newContent } })
});
console.log(await updateResp.json());`;
    }

    if (lang === "ruby") {
      return `require 'net/http'
require 'json'
require 'uri'

BASE_URL = "${baseUrl}"
TOKEN = "${tokenStr}"
PAGE_ID = "${pageIdStr}"

uri = URI("#{BASE_URL}/api/pages/#{PAGE_ID}/")
http = Net::HTTP.new(uri.host, uri.port)
http.use_ssl = uri.scheme == 'https'

# Get current content
get_req = Net::HTTP::Get.new(uri)
get_req["Authorization"] = "Bearer #{TOKEN}"
page = JSON.parse(http.request(get_req).body)
current_content = page.dig("details", "content") || ""

# Append new content
new_content = current_content + "\\n\\nNew content to append"
put_req = Net::HTTP::Put.new(uri)
put_req["Authorization"] = "Bearer #{TOKEN}"
put_req["Content-Type"] = "application/json"
put_req.body = { details: { content: new_content } }.to_json

puts JSON.parse(http.request(put_req).body)`;
    }

    if (lang === "php") {
      return `<?php
$baseUrl = "${baseUrl}";
$token = "${tokenStr}";
$pageId = "${pageIdStr}";

$url = "$baseUrl/api/pages/$pageId/";

// Get current content
$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => ["Authorization: Bearer $token"]
]);
$page = json_decode(curl_exec($ch), true);
$currentContent = $page["details"]["content"] ?? "";

// Append new content
$newContent = $currentContent . "\\n\\nNew content to append";
curl_setopt_array($ch, [
    CURLOPT_CUSTOMREQUEST => "PUT",
    CURLOPT_HTTPHEADER => [
        "Authorization: Bearer $token",
        "Content-Type: application/json"
    ],
    CURLOPT_POSTFIELDS => json_encode(["details" => ["content" => $newContent]])
]);
print_r(json_decode(curl_exec($ch), true));
curl_close($ch);`;
    }

    if (lang === "go") {
      return `package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

const (
    baseURL = "${baseUrl}"
    token   = "${tokenStr}"
    pageID  = "${pageIdStr}"
)

func main() {
    url := baseURL + "/api/pages/" + pageID + "/"
    client := &http.Client{}

    // Get current content
    getReq, _ := http.NewRequest("GET", url, nil)
    getReq.Header.Set("Authorization", "Bearer "+token)
    getResp, _ := client.Do(getReq)
    var page map[string]interface{}
    json.NewDecoder(getResp.Body).Decode(&page)
    getResp.Body.Close()
    currentContent, _ := page["details"].(map[string]interface{})["content"].(string)

    // Append new content
    newContent := currentContent + "\\n\\nNew content to append"
    body, _ := json.Marshal(map[string]interface{}{
        "details": map[string]string{"content": newContent},
    })
    putReq, _ := http.NewRequest("PUT", url, bytes.NewBuffer(body))
    putReq.Header.Set("Authorization", "Bearer "+token)
    putReq.Header.Set("Content-Type", "application/json")
    putResp, _ := client.Do(putReq)
    defer putResp.Body.Close()

    var result map[string]interface{}
    json.NewDecoder(putResp.Body).Decode(&result)
    fmt.Println(result)
}`;
    }
  }

  async function copyToClipboard(code) {
    try {
      await navigator.clipboard.writeText(code);
      showToast("Copied to clipboard!");
    } catch (err) {
      console.error("Failed to copy:", err);
      showToast("Failed to copy", "error");
    }
  }

  function handleClickOutside(e) {
    if (otherDropdownOpen && !e.target.closest('.other-dropdown-container')) {
      otherDropdownOpen = false;
    }
  }

  onMount(() => {
    fetchApiToken();

    registerPageChangeHandler((pageId) => {
      currentPageId = pageId;
      if (pageId) {
        currentProjectId = findProjectForPage(pageId);
      } else {
        currentProjectId = null;
      }
    });

    if (sidebarState.currentPageId) {
      currentPageId = sidebarState.currentPageId;
      currentProjectId = findProjectForPage(currentPageId);
    }

    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  });

  $effect(() => {
    if (typeof window !== "undefined" && window.getCurrentPage) {
      const currentPage = window.getCurrentPage();
      if (currentPage?.external_id && currentPage.external_id !== currentPageId) {
        currentPageId = currentPage.external_id;
        currentProjectId = findProjectForPage(currentPageId);
      }
    }
  });
</script>

<div class="dev-content">
  {#if loading}
    <div class="dev-loading">Loading...</div>
  {:else}
    <div class="dev-scrollable">
      <div class="lang-switcher">
      {#each mainLanguages as lang (lang.id)}
        <button
          class="lang-btn"
          class:active={selectedLang === lang.id}
          onclick={() => selectLanguage(lang.id)}
        >
          {lang.label}
        </button>
      {/each}
      <div class="other-dropdown-container">
        <button
          class="lang-btn other-btn"
          class:active={isOtherLanguage(selectedLang)}
          onclick={toggleOtherDropdown}
        >
          {isOtherLanguage(selectedLang) ? getSelectedOtherLabel() : "Other"}
          <svg class="dropdown-arrow" class:open={otherDropdownOpen} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>
        {#if otherDropdownOpen}
          <div class="other-dropdown">
            {#each otherLanguages as lang (lang.id)}
              <button
                class="other-dropdown-item"
                class:active={selectedLang === lang.id}
                onclick={() => selectLanguage(lang.id)}
              >
                {lang.label}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>

    {#if !apiToken}
      <div class="dev-warning">
        <span class="warning-icon">⚠️</span>
        <span>API token not available. Visit <a href="/settings#developer">Settings</a> to view your token.</span>
      </div>
    {/if}

    <div class="code-sections">
      <div class="section-group">
        <h2 class="section-title">This Project</h2>
        <div class="code-section">
          <div class="code-section-header">
            <h3>Create a new page</h3>
            <button
              class="copy-btn"
              title="Copy to clipboard"
              onclick={() => copyToClipboard(generateCreatePageCode(selectedLang, currentProjectId, apiToken))}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy
            </button>
          </div>
          <pre class="code-block"><code>{generateCreatePageCode(selectedLang, currentProjectId, apiToken)}</code></pre>
        </div>

        <div class="code-section">
          <div class="code-section-header">
            <h3>List all pages</h3>
            <button
              class="copy-btn"
              title="Copy to clipboard"
              onclick={() => copyToClipboard(generateListPagesCode(selectedLang, currentProjectId, apiToken))}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy
            </button>
          </div>
          <pre class="code-block"><code>{generateListPagesCode(selectedLang, currentProjectId, apiToken)}</code></pre>
        </div>
      </div>

      <div class="section-group">
        <h2 class="section-title">This Page</h2>
        <div class="code-section">
          <div class="code-section-header">
            <h3>Get content</h3>
            <button
              class="copy-btn"
              title="Copy to clipboard"
              onclick={() => copyToClipboard(generateGetPageCode(selectedLang, currentPageId, apiToken))}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy
            </button>
          </div>
          <pre class="code-block"><code>{generateGetPageCode(selectedLang, currentPageId, apiToken)}</code></pre>
        </div>

        <div class="code-section">
          <div class="code-section-header">
            <h3>Append content</h3>
            <button
              class="copy-btn"
              title="Copy to clipboard"
              onclick={() => copyToClipboard(generateAppendPageCode(selectedLang, currentPageId, apiToken))}
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              Copy
            </button>
          </div>
          <pre class="code-block"><code>{generateAppendPageCode(selectedLang, currentPageId, apiToken)}</code></pre>
        </div>
      </div>
    </div>
    </div>

    <div class="dev-footer">
      <a href="/dev/" target="_blank" rel="noopener noreferrer" class="api-docs-link">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
          <polyline points="15 3 21 3 21 9"></polyline>
          <line x1="10" y1="14" x2="21" y2="3"></line>
        </svg>
        Developer Portal
      </a>
    </div>
  {/if}
</div>

<style>
  .dev-content {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dev-scrollable {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 1rem;
    padding-bottom: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .dev-loading {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-secondary);
  }

  .lang-switcher {
    display: flex;
    gap: 0.25rem;
    background: rgba(55, 53, 47, 0.04);
    padding: 0.25rem;
    border-radius: 8px;
  }

  .lang-btn {
    flex: 1;
    padding: 0.5rem 0.75rem;
    border: none;
    background: transparent;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
  }

  .lang-btn:hover {
    color: var(--text-primary);
  }

  .lang-btn.active {
    background: white;
    color: var(--text-primary);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  }

  .other-dropdown-container {
    position: relative;
    flex: 1;
  }

  .other-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    width: 100%;
  }

  .dropdown-arrow {
    width: 12px;
    height: 12px;
    transition: transform 0.15s;
  }

  .dropdown-arrow.open {
    transform: rotate(180deg);
  }

  .other-dropdown {
    position: absolute;
    top: calc(100% + 0.25rem);
    left: 0;
    right: 0;
    background: white;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: 100;
    overflow: hidden;
  }

  .other-dropdown-item {
    display: block;
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: none;
    background: transparent;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    text-align: left;
    transition: all 0.1s;
  }

  .other-dropdown-item:hover {
    background: rgba(55, 53, 47, 0.04);
    color: var(--text-primary);
  }

  .other-dropdown-item.active {
    background: rgba(35, 131, 226, 0.1);
    color: #2383e2;
  }

  .dev-warning {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem;
    background: #fffbeb;
    border: 1px solid #fcd34d;
    border-radius: 8px;
    font-size: 0.85rem;
    color: #92400e;
  }

  .dev-warning a {
    color: #b45309;
    font-weight: 500;
  }

  .warning-icon {
    flex-shrink: 0;
  }

  .code-sections {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .section-group {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .section-title {
    margin: 0;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    opacity: 0.7;
  }

  .code-section {
    background: rgba(55, 53, 47, 0.04);
    border-radius: 8px;
    overflow: hidden;
  }

  .code-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid rgba(55, 53, 47, 0.08);
  }

  .code-section-header h3 {
    margin: 0;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-primary);
  }

  .copy-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    border: none;
    background: white;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  }

  .copy-btn:hover {
    color: var(--text-primary);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }

  .copy-btn svg {
    width: 14px;
    height: 14px;
  }

  .code-block {
    margin: 0;
    padding: 1rem;
    overflow-x: auto;
    font-family: "SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, monospace;
    font-size: 0.75rem;
    line-height: 1.5;
    color: var(--text-primary);
    white-space: pre-wrap;
    word-break: break-all;
  }

  .code-block code {
    font-family: inherit;
  }

  .dev-footer {
    flex-shrink: 0;
    padding: 1rem;
    border-top: 1px solid var(--border-light);
    background: var(--bg-primary, white);
  }

  .api-docs-link {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: rgba(35, 131, 226, 0.1);
    border-radius: 8px;
    color: #2383e2;
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    transition: background 0.15s;
  }

  .api-docs-link:hover {
    background: rgba(35, 131, 226, 0.15);
  }

  .api-docs-link svg {
    width: 16px;
    height: 16px;
  }
</style>
