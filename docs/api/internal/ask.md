# Ask API

## Table of Contents

- [Ask a question](#ask-a-question)

## Ask a question

Submit a question about your pages and receive an AI-generated answer based on relevant page content.

### URL

`/api/ask/`

### HTTP Method

`POST`

### Path Params

None

### Query Params

None

### Data Params

```json
{
  "query": "What are my meeting pages about?",
  "page_ids": ["abc123", "def456"]
}
```

- `query` (String, required): The question to ask. Min length: 1, Max length: 10,000 characters.
- `page_ids` (Array of Strings, optional): List of page external_ids to explicitly include in the context. If provided, these pages are prioritized over mention parsing and similarity search. Default: []

### Authorization

Requires authentication. See [Overview](./overview.md) for details on session-based authentication.

### Request Headers

See [Overview](./overview.md)

### Response

#### Success Response (200 OK)

```json
{
  "answer": "Your meeting pages cover the Q4 planning session and the product roadmap review. The Q4 planning focused on resource allocation and timeline adjustments, while the roadmap review discussed upcoming feature releases.",
  "pages": [
    {
      "external_id": "abc123",
      "title": "Q4 Planning Meeting",
      "updated": "2025-01-15T10:30:00Z",
      "created": "2025-01-10T08:00:00Z",
      "modified": "2025-01-15T10:30:00Z"
    },
    {
      "external_id": "def456",
      "title": "Product Roadmap Review",
      "updated": "2025-01-14T14:20:00Z",
      "created": "2025-01-12T09:00:00Z",
      "modified": "2025-01-14T14:20:00Z"
    }
  ]
}
```

**Notes:**

- The `answer` field contains the AI-generated response to your query
- The `pages` array lists the pages that were used to generate the answer, ordered by relevance
- Up to 10 pages maximum will be used to generate the answer

#### Error Response (400 Bad Request)

Returned when the query processing fails. The error code and message vary based on the failure reason:

**Empty Question:**

```json
{
  "error": "empty_question",
  "message": "Blank or empty question"
}
```

Returned when the query is blank or contains only whitespace (after mention parsing).

**No Matching Pages:**

```json
{
  "error": "no_matching_pages",
  "message": "No matching pages"
}
```

Returned when no pages match the query (either via explicit page_ids, mentions, or similarity search).

**API Error:**

```json
{
  "error": "api_error",
  "message": "API returned an error"
}
```

Returned when the LLM API encounters an error (rate limits, service unavailable, etc.).

**Unexpected Error:**

```json
{
  "error": "unexpected",
  "message": "Unable to process question"
}
```

Returned when an unexpected error occurs during query processing.

#### Error Response (422 Unprocessable Entity)

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

Returned when the request body validation fails (e.g., empty query or query exceeding max length).

#### Error Response (503 Service Unavailable)

```json
{
  "error": "ask_feature_disabled",
  "message": "This feature is not available at this time."
}
```

Returned when the ask feature is disabled via the `ASK_FEATURE_ENABLED` setting.

### Behavior Details

The ask endpoint processes queries using a Retrieval-Augmented Generation (RAG) pipeline:

1. **Note Selection** (in priority order):

   - **Explicit page_ids**: If `page_ids` is provided, these pages are used first
   - **Mention parsing**: Extracts `@[title](id)` mentions from the query
   - **Similarity search**: If no pages are explicitly specified, uses vector similarity to find relevant pages

2. **Priority and Merging**:

   - `page_ids` parameter takes highest priority
   - Mentions from query text are added next
   - Duplicates are automatically removed
   - The total is limited to 10 pages maximum (configured via `ASK_EMBEDDINGS_MAX_PAGES`)

3. **Answer Generation**:
   - Selected pages are sent to the LLM with the cleaned query
   - The LLM generates an answer based on the page content
   - The response includes both the answer and the list of pages used

### Example Usage

#### Basic Query (Similarity Search)

```bash
POST /api/ask/
Content-Type: application/json

{
  "query": "What did we discuss in yesterday's meeting?"
}
```

The system will automatically find relevant pages using vector similarity.

#### Query with Explicit Pages

```bash
POST /api/ask/
Content-Type: application/json

{
  "query": "Summarize the key points",
  "page_ids": ["abc123", "def456", "ghi789"]
}
```

Only the specified pages will be used to generate the answer.

#### Query with Mentions

```bash
POST /api/ask/
Content-Type: application/json

{
  "query": "Compare @[Q3 Review](abc123) with @[Q4 Planning](def456)"
}
```

The mentioned pages will be used to generate the answer. Note titles are preserved in the query for semantic context.

#### Mixed: Explicit Pages + Mentions

```bash
POST /api/ask/
Content-Type: application/json

{
  "query": "What are the action items from @[Daily Standup](xyz789)?",
  "page_ids": ["abc123"]
}
```

Both explicit `page_ids` and parsed mentions will be used, with `page_ids` taking priority.

---
