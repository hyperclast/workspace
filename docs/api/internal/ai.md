# AI Providers API

Endpoints for managing AI provider configurations (OpenAI, Anthropic, Google, custom OpenAI-compatible) at user and organization scope. Configs hold the API key, optional base URL, optional pinned model, and the validated/enabled/default flags that control which key the rest of the app picks up.

## Table of Contents

- [Idempotency & Identity](#idempotency--identity)
- [Error Body Shape](#error-body-shape)
- [List user provider configs](#list-user-provider-configs)
- [Create or update a user provider config](#create-or-update-a-user-provider-config)
- [Retrieve a user provider config](#retrieve-a-user-provider-config)
- [Update a user provider config](#update-a-user-provider-config)
- [Delete a user provider config](#delete-a-user-provider-config)
- [Validate a user provider config](#validate-a-user-provider-config)
- [List org provider configs](#list-org-provider-configs)
- [Create or update an org provider config](#create-or-update-an-org-provider-config)
- [Update an org provider config](#update-an-org-provider-config)
- [Delete an org provider config](#delete-an-org-provider-config)
- [Validate an org provider config](#validate-an-org-provider-config)

## Idempotency & Identity

The provider-config endpoints use a stable identity tuple:

```
(scope, provider, api_key, api_base_url)
```

- `scope` is the owning user (for `/api/v1/ai/providers/...`) or the owning org (for `/api/v1/ai/orgs/{org_id}/providers/...`). Identity never crosses scopes — a user POST never matches an org row, and vice versa.
- `provider` is the catalog identifier (`openai`, `anthropic`, `google`, `custom`).
- `api_key` is the secret. An empty/missing `api_key` is treated as no dedup key — those rows are never matched.
- `api_base_url` is the optional override. Built-in providers store the empty string; `custom` provider rows that point at different base URLs are distinct identities.

### POST is an upsert (status 201 in either case)

Hitting `POST` with an identity that already exists in the same scope updates the existing row instead of creating a new one. The same `201 Created` status is returned whether the row is new or refreshed; the response body is the (possibly updated) config either way. Distinguish by checking `external_id` against rows you already know about, or by reading `modified`.

When the matched row is updated, payload values overwrite metadata (`display_name`, `api_base_url`, `model_name`) only when they are non-empty. The flags `is_enabled` and `is_default` are applied only when the client sends them explicitly — omitting them preserves the row's previous state. Validation re-runs whenever the existing row is unvalidated, or whenever a validation-relevant field (`api_key`, `api_base_url`, `model_name`) changes against a previously-validated row.

### PATCH rejects identity collisions (status 400)

`PATCH` does not auto-merge. If the resulting `(api_key, api_base_url)` pair would collide with another row in the same scope, the endpoint returns `400` with the colliding row in the body and leaves the target row untouched. Resolve by deleting one of the rows or by patching different identity values.

## Error Body Shape

Validation failures from `POST` and identity collisions from `PATCH` use the same envelope:

```json
{
  "message": "Human-readable description of why the request failed",
  "config": {
    "external_id": "abc123",
    "provider": "openai",
    "display_name": "My Key",
    "has_key": true,
    "key_hint": "sk-...mnop",
    "api_base_url": null,
    "model_name": null,
    "is_enabled": true,
    "is_default": false,
    "is_validated": false,
    "last_validated_at": null,
    "scope": "user",
    "created": "2026-04-01T12:00:00Z",
    "modified": "2026-04-15T08:30:00Z"
  }
}
```

- `message` is always present.
- `config` is the existing row that the client should reconcile against (either the row that just failed validation, or the colliding row in the PATCH case).
- The plaintext `api_key` is **never** included. Use `key_hint` (`****` for short keys, `xxx...yyyy` otherwise) for fingerprint-style identification.

The standard `error` and `detail` fields described in [Overview](./overview.md) are also present alongside `message` and `config`.

---

## List user provider configs

List the authenticated user's personal AI provider configurations.

### URL

`/api/v1/ai/providers/`

### HTTP Method

`GET`

### Authorization

Requires authentication.

### Response

- Status Code: 200
- Schema: array of provider config objects (same shape as the `config` body above).

---

## Create or update a user provider config

Idempotent upsert. See [Idempotency & Identity](#idempotency--identity) for matching rules.

### URL

`/api/v1/ai/providers/`

### HTTP Method

`POST`

### Authorization

Requires authentication.

### Data Params

- `provider` (String, required): One of `openai`, `anthropic`, `google`, `custom`.
- `api_key` (String, optional): The provider key. Empty/missing means no dedup key — every POST without a key creates a new row.
- `api_base_url` (String, optional): URL override. Required in practice for `custom`; empty for built-ins.
- `model_name` (String, optional): Pinned model identifier.
- `display_name` (String, optional): Friendly label (max 100 chars).
- `is_enabled` (Boolean, optional): Defaults to `true` for new rows; preserved when omitted on a re-POST.
- `is_default` (Boolean, optional): Defaults to `false` for new rows; preserved when omitted on a re-POST.

### Response (created or updated)

- Status Code: 201
- Schema: the resulting config row.

### Response (validation failed)

- Status Code: 400
- Schema:

```json
{
  "message": "API key validation failed: <reason>",
  "config": { ... }
}
```

The row exists in the database (so a future POST can re-attempt validation against the same identity) but is `is_validated: false`. See [Error Body Shape](#error-body-shape).

---

## Retrieve a user provider config

### URL

`/api/v1/ai/providers/{config_id}/`

### HTTP Method

`GET`

### Path Params

- `config_id` (String, required): The config's `external_id`.

### Response

- Status Code: 200
- Schema: provider config object.

### Error Responses

- 404 — Config not found or owned by another user.

---

## Update a user provider config

Update fields on an existing row. Send only the fields you want to change.

### URL

`/api/v1/ai/providers/{config_id}/`

### HTTP Method

`PATCH`

### Path Params

- `config_id` (String, required)

### Data Params

All optional. Send only the fields you want to change:

- `display_name`, `api_key`, `api_base_url`, `model_name`, `is_enabled`, `is_default`.

Sending `api_key` always flips `is_validated` to `false` and triggers a fresh validation against the provider.

### Response

- Status Code: 200
- Schema: updated config.

### Error Responses

- 400 — Validation failed (same envelope as POST).
- 400 — The post-PATCH `(api_key, api_base_url)` pair would collide with another row in the same scope. Body:

  ```json
  {
    "message": "Another configuration with this api_key and api_base_url already exists in this scope. Delete or merge it manually before patching.",
    "config": { ...the colliding row... }
  }
  ```

  The target row is **not** modified when a collision is detected. Resolve by deleting the colliding row or by patching different identity values.

- 404 — Config not found.

---

## Delete a user provider config

### URL

`/api/v1/ai/providers/{config_id}/`

### HTTP Method

`DELETE`

### Response

- Status Code: 204 — Deleted.

### Error Responses

- 404 — Config not found.

---

## Validate a user provider config

Re-runs key validation against the provider and updates `is_validated` / `last_validated_at` on the row.

### URL

`/api/v1/ai/providers/{config_id}/validate/`

### HTTP Method

`POST`

### Response

- Status Code: 200
- Schema:

```json
{
  "is_valid": true,
  "error": null
}
```

When validation fails, `is_valid` is `false` and `error` is a human-readable string.

---

## List org provider configs

Admin-only listing of an organization's AI provider configs.

### URL

`/api/v1/ai/orgs/{org_id}/providers/`

### HTTP Method

`GET`

### Authorization

Requires authentication and org-admin role.

### Response

- Status Code: 200
- Schema: array of provider config objects scoped to the org.

### Error Responses

- 403 — Caller is not an admin of the org.
- 404 — Org not found.

A read-only summary is also available to all org members at `/api/v1/ai/orgs/{org_id}/providers/summary/`. That endpoint omits keys, base URLs, model names, and `external_id`.

---

## Create or update an org provider config

Idempotent upsert at org scope. Identity matches `(org, provider, api_key, api_base_url)`. See [Idempotency & Identity](#idempotency--identity).

### URL

`/api/v1/ai/orgs/{org_id}/providers/`

### HTTP Method

`POST`

### Authorization

Requires authentication and org-admin role.

### Data Params

Same as the user-scope create endpoint.

### Response (created or updated)

- Status Code: 201

### Error Responses

- 400 — Validation failed (envelope identical to user-scope POST).
- 403 — Not an admin.
- 404 — Org not found.

---

## Update an org provider config

### URL

`/api/v1/ai/orgs/{org_id}/providers/{config_id}/`

### HTTP Method

`PATCH`

### Authorization

Org-admin only.

### Data Params

Same as user-scope PATCH.

### Response

- Status Code: 200

### Error Responses

- 400 — Validation failed, or the post-PATCH `(api_key, api_base_url)` pair would collide with another row in the same org (same envelope and behavior as user-scope PATCH).
- 403 — Not an admin.
- 404 — Org or config not found.

---

## Delete an org provider config

### URL

`/api/v1/ai/orgs/{org_id}/providers/{config_id}/`

### HTTP Method

`DELETE`

### Authorization

Org-admin only.

### Response

- Status Code: 204

### Error Responses

- 403 — Not an admin.
- 404 — Org or config not found.

---

## Validate an org provider config

### URL

`/api/v1/ai/orgs/{org_id}/providers/{config_id}/validate/`

### HTTP Method

`POST`

### Authorization

Org-admin only.

### Response

Same shape as the user-scope validate endpoint.

### Error Responses

- 403 — Not an admin.
- 404 — Org or config not found.
