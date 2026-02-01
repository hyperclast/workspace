# Data Import System

This document describes the architecture and design of the data import feature in Hyperclast.

## Overview

The `imports` app enables users to migrate content from external note-taking applications into Hyperclast projects. The system is designed to be provider-agnostic, currently supporting Notion with plans for Obsidian.

**Supported Providers:**

- **Notion** - Markdown & CSV export format
- **Obsidian** - Planned (vault export)

## Access Control

Since imports create pages, they require **editor (write) permission** on the target project:

| Permission Level                  | Can Import? |
| --------------------------------- | ----------- |
| Org admin                         | Yes         |
| Org member (with access enabled)  | Yes         |
| Project editor with `editor` role | Yes         |
| Project editor with `viewer` role | **No**      |
| Page-only editor (Tier 3)         | **No**      |

**Why viewers cannot import:**

Imports create new pages in the target project. This is a write operation that requires the same permissions as creating a page manually. Project editors with `viewer` role have read-only access and cannot create or modify content.

The API returns HTTP 403 (Forbidden) with the message "You do not have permission to create pages in this project" when a viewer attempts to start an import.

## Architecture

### Models

```
ImportJob
  └─ archive: ImportArchive (1:1)
  └─ imported_pages: ImportedPage[] (1:N)
  └─ abuse_record: ImportAbuseRecord (1:1, optional)
  └─ project: Project (N:1)
  └─ user: User (N:1)

ImportBannedUser
  └─ user: User (1:1)
```

**ImportJob** (`imports/models/jobs.py`)

- Tracks a single import operation
- Status: `pending` → `processing` → `completed`/`failed`
- Counters: `total_pages`, `pages_imported_count`, `pages_skipped_count`, `pages_failed_count`
- Provider field supports multiple sources

**ImportArchive** (`imports/models/archives.py`)

- Stores the original export file in R2 for audit/debugging
- One-to-one with ImportJob
- Contains temp file path (pre-processing) and R2 location (post-processing)

**ImportedPage** (`imports/models/pages.py`)

- Links an import job to the created Page
- `original_path`: Preserves source hierarchy (e.g., `Parent/Child.md`)
- `source_hash`: Provider-specific identifier for deduplication
- Unique constraint: `(project, source_hash)`

**ImportAbuseRecord** (`imports/models/abuse.py`)

- Logs security violations (zip bombs, malicious archives)
- One-to-one with ImportJob (optional, only created on violation)
- Severity levels: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- Stores violation details, IP address, user agent

**ImportBannedUser** (`imports/models/bans.py`)

- Permanent import ban for a user
- Created automatically when abuse thresholds are exceeded
- `enforced`: Can be toggled via Django admin to lift bans
- One-to-one with User

### Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         Client                                    │
├──────────────────────────────────────────────────────────────────┤
│  1. POST /api/imports/notion/                                    │
│     - project_id + zip file (multipart/form-data)                │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                      API Handler                                  │
├──────────────────────────────────────────────────────────────────┤
│  2. Verify user has editor permission (user_can_edit_in_project) │
│  3. Check if user is banned (ImportBannedUser.enforced=True)     │
│  4. Validate file type, file size                                │
│  5. Create ImportJob (status: pending) with request context      │
│  6. Save file to temp directory                                  │
│  7. Create ImportArchive with temp_file_path                     │
│  8. Enqueue process_notion_import task                           │
│  9. Return job ID immediately                                    │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Background Task (RQ)                          │
├──────────────────────────────────────────────────────────────────┤
│ 10. Update status to 'processing'                                │
│ 11. Pre-extraction safety check (zip bomb detection)             │
│ 12. Extract zip safely with streaming extraction                 │
│ 13. Parse markdown/CSV files into ParsedPage objects             │
│ 14. Flatten nested structure                                     │
│ 15. Query existing source_hash values for deduplication          │
│ 16. Create Page objects in batches                               │
│ 17. Create ImportedPage records                                  │
│ 18. Remap internal links to Hyperclast format                    │
│ 19. Archive original zip to R2                                   │
│ 20. Delete temp file                                             │
│ 21. Update status to 'completed' with counts                     │
└──────────────────────────────────────────────────────────────────┘
```

## Deduplication

The system prevents duplicate imports using `source_hash`:

| Provider | source_hash Value  | Example                     |
| -------- | ------------------ | --------------------------- |
| Notion   | Hash from filename | `abc123def456789012`        |
| Obsidian | Relative filepath  | `Daily Notes/2024-01-15.md` |

**Behavior:**

- First import: All pages created
- Re-import same zip: All pages skipped (100% dedup)
- Same zip to different project: All pages created (projects are independent)
- Updated export: Only new pages created

**Constraint:** `UNIQUE (project_id, source_hash) WHERE source_hash != ''`

Pages without identifiable hashes (rare) can be duplicated.

## Notion Export Format

### File Structure

Notion exports can be nested:

```
Export-XXXXXXXX.zip
└── ExportBlock-{uuid}-Part-1.zip     ← Inner zip (auto-extracted)
    ├── Page Name abc123def456.md     ← Title + 16-32 char hash
    ├── Page Name/                    ← TITLE ONLY (no hash!)
    │   ├── Child def456abc789.md
    │   └── Child/
    │       └── Grandchild ghi789.md
    └── Database abc123.csv
```

**Key observations:**

- Outer zip may contain `ExportBlock-*-Part-*.zip` files (auto-extracted)
- Filenames include hash: `{Title} {hash}.md`
- Folders use title only: `{Title}/` (not `{Title} {hash}/`)
- Large exports split into Part-1, Part-2, etc.

### Content Transformation

| Notion Block  | Markdown         | Hyperclast            |
| ------------- | ---------------- | --------------------- |
| Heading 1-3   | `# ## ###`       | Preserved             |
| Paragraph     | Plain text       | Preserved             |
| Bullet list   | `- item`         | Preserved             |
| Numbered list | `1. item`        | Preserved             |
| Toggle        | `<details>` HTML | Nested list           |
| Callout       | `<aside>` HTML   | Blockquote with emoji |
| Code          | ` ```lang ``` `  | Preserved             |
| Quote         | `> text`         | Preserved             |
| Table         | Markdown table   | Preserved             |
| To-do         | `- [ ] task`     | Preserved             |
| Image         | `![](path)`      | Preserved             |

### Link Remapping

Internal Notion links are remapped to Hyperclast format:

```markdown
# Before (Notion export)

[See notes](My%20Notes%20abc123def456.md)

# After (Hyperclast)

[See notes](/pages/550e8400-e29b-41d4-a716-446655440000/)
```

The remapping process:

1. Extract link target from markdown
2. Parse filename to get `source_hash`
3. Look up existing `ImportedPage` by hash (includes previously-imported pages)
4. Replace with Hyperclast `/pages/{external_id}/` format
5. Links to unknown pages are preserved as-is

## Configuration

| Variable                               | Default           | Description              |
| -------------------------------------- | ----------------- | ------------------------ |
| `WS_IMPORTS_MAX_FILE_SIZE_BYTES`       | 104857600 (100MB) | Maximum upload size      |
| `WS_IMPORTS_TEMP_DIR`                  | `/tmp`            | Temporary file storage   |
| `WS_IMPORTS_STORAGE_PROVIDER`          | `r2`              | Archive storage provider |
| `WS_IMPORTS_RATE_LIMIT_REQUESTS`       | 10                | Rate limit per window    |
| `WS_IMPORTS_RATE_LIMIT_WINDOW_SECONDS` | 3600              | Rate limit window        |

### Security Configuration

| Variable                                 | Default          | Description                    |
| ---------------------------------------- | ---------------- | ------------------------------ |
| `WS_IMPORTS_MAX_UNCOMPRESSED_SIZE_BYTES` | 5368709120 (5GB) | Max total uncompressed size    |
| `WS_IMPORTS_MAX_COMPRESSION_RATIO`       | 30.0             | Max compression ratio allowed  |
| `WS_IMPORTS_MAX_FILE_COUNT`              | 100000           | Max files in archive           |
| `WS_IMPORTS_MAX_SINGLE_FILE_SIZE_BYTES`  | 1073741824 (1GB) | Max single file size           |
| `WS_IMPORTS_MAX_PATH_DEPTH`              | 30               | Max directory depth            |
| `WS_IMPORTS_MAX_NESTED_ZIP_DEPTH`        | 2                | Max nested zip depth           |
| `WS_IMPORTS_EXTRACTION_TIMEOUT_SECONDS`  | 300              | Extraction timeout (5 minutes) |
| `WS_IMPORTS_ABUSE_WINDOW_DAYS`           | 7                | Days to look back for abuse    |
| `WS_IMPORTS_ABUSE_CRITICAL_THRESHOLD`    | 1                | CRITICAL violations to ban     |
| `WS_IMPORTS_ABUSE_HIGH_THRESHOLD`        | 2                | HIGH violations to ban         |
| `WS_IMPORTS_ABUSE_MEDIUM_THRESHOLD`      | 5                | MEDIUM violations to ban       |
| `WS_IMPORTS_ABUSE_LOW_THRESHOLD`         | 10               | LOW violations to ban          |

## Security

The import system includes multiple layers of protection against malicious archives.

### Pre-extraction Inspection

Before extracting any content, archives are inspected using zipfile metadata:

- **Compression ratio limit** (default: 30x) - Prevents zip bombs
- **Maximum uncompressed size** (default: 5GB) - Limits resource usage
- **Maximum file count** (default: 100,000) - Prevents file system exhaustion
- **Maximum single file size** (default: 1GB) - Limits memory usage
- **Maximum path depth** (default: 30) - Prevents deeply nested structures
- **Nested zip detection** - Only allows Notion's `ExportBlock-*-Part-*.zip` pattern

### Streaming Extraction

During extraction, additional protections apply:

- **Chunked reading** - Limits memory usage during extraction
- **Path traversal prevention** - Blocks `../` and absolute paths
- **Extraction timeout** (default: 5 minutes) - Prevents resource exhaustion
- **Fail-fast behavior** - Stops immediately on any violation

### Abuse Tracking

Violations are logged with severity levels:

| Severity | Trigger                             | Default Threshold |
| -------- | ----------------------------------- | ----------------- |
| CRITICAL | Compression ratio > 100x            | 1 violation = ban |
| HIGH     | Ratio > 50x or nested archive abuse | 2 violations      |
| MEDIUM   | Standard threshold violations       | 5 violations      |
| LOW      | Minor/edge-case violations          | 10 violations     |

### User Banning

When thresholds are exceeded within the configured window (default: 7 days):

1. An `ImportBannedUser` record is created
2. User receives HTTP 429 on future import attempts
3. Bans are permanent but can be lifted via Django admin
4. If a lifted ban's user violates again, the ban is re-enabled

## API Endpoints

| Endpoint                   | Method | Description         |
| -------------------------- | ------ | ------------------- |
| `/api/imports/`            | GET    | List import jobs    |
| `/api/imports/notion/`     | POST   | Start Notion import |
| `/api/imports/{id}/`       | GET    | Get job status      |
| `/api/imports/{id}/pages/` | GET    | List imported pages |
| `/api/imports/{id}/`       | DELETE | Delete job record   |

See `docs/api/internal/imports.md` for detailed API documentation.

## Job Queue

Import processing uses a dedicated RQ queue:

- **Queue name:** `imports`
- **Timeout:** 600 seconds (10 minutes)
- **Retry policy:** None (failures are logged, job marked as failed)

The separate queue prevents large imports from blocking other background tasks.

## Error Handling

| Error              | Handling                                  |
| ------------------ | ----------------------------------------- |
| Invalid zip        | Job fails with `ImportInvalidZipError`    |
| Empty/no content   | Job fails with `ImportNoContentError`     |
| File too large     | Rejected at API level (413)               |
| Zip bomb detected  | Job fails with `ImportArchiveBombError`   |
| Path traversal     | Job fails with `ImportArchiveBombError`   |
| Extraction timeout | Job fails with `ImportArchiveBombError`   |
| User banned        | Rejected at API level (429)               |
| Corrupt content    | Individual pages skipped, others continue |
| R2 archive fails   | Job completes, archive marked failed      |

**Empty/No Content Detection:**

An import job is marked as failed (not completed) when the archive contains no importable content. This occurs when:

- The zip file is completely empty (no files)
- The zip contains only unsupported file types (e.g., images, PDFs, plain text files)
- No markdown (.md) or CSV (.csv) files are found

This ensures users receive clear feedback when they accidentally upload an incorrect export or empty archive. Note that re-importing the same content (full deduplication) is still considered successful, since the system found valid content that was already imported.

The system is designed to be resilient - individual page failures don't stop the entire import. Security violations result in immediate failure and abuse tracking.

## Future: Obsidian Support

The architecture supports Obsidian imports with minimal changes:

1. Add `OBSIDIAN = "obsidian"` to `ImportProvider`
2. Create `imports/services/obsidian.py` with vault parsing
3. Add `POST /api/imports/obsidian/` endpoint
4. Use relative filepath as `source_hash`

Obsidian-specific considerations:

- Wiki-style links: `[[Page Name]]` → `[Page Name](/pages/{id}/)`
- Frontmatter parsing for metadata
- Attachment handling
- Plugin-specific markdown extensions

See `CLAUDE.obsidian_dedupe.md` for deduplication strategy details.

## Key Files

| File                                 | Purpose                              |
| ------------------------------------ | ------------------------------------ |
| `imports/models/jobs.py`             | ImportJob model                      |
| `imports/models/archives.py`         | ImportArchive for R2 storage         |
| `imports/models/pages.py`            | ImportedPage with deduplication      |
| `imports/models/abuse.py`            | ImportAbuseRecord for abuse tracking |
| `imports/models/bans.py`             | ImportBannedUser for permanent bans  |
| `imports/api/imports.py`             | REST API endpoints                   |
| `imports/services/notion.py`         | Notion parsing and transformation    |
| `imports/services/archive_safety.py` | Archive inspection and validation    |
| `imports/services/abuse.py`          | Abuse tracking and ban enforcement   |
| `imports/tasks.py`                   | Background job processing            |
| `imports/throttling.py`              | Rate limiting                        |
| `imports/exceptions.py`              | Custom exceptions                    |
