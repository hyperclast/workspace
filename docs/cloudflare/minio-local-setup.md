# MinIO R2 Emulator Setup

MinIO provides an S3-compatible storage service that emulates Cloudflare R2 for local development. This allows you to test file uploads, imports, and other R2-dependent features without a real R2 account.

## Quick Start (Docker Stack)

The easiest way to use MinIO is with the full Docker stack:

```bash
./run-stack.sh --minio 9800
```

This starts all services (web, db, redis, rq) plus MinIO, with R2 configuration automatically injected. No additional `.env` configuration needed. The file upload feature (`WS_FILEHUB_FEATURE_ENABLED`) is automatically enabled.

- Web app: http://localhost:9800
- MinIO S3 API: http://localhost:9000
- MinIO Console: http://localhost:9001 (user: `minioadmin`, password: `minioadmin`)

## Standalone Setup (Non-Docker Development)

If you're running Django directly with `runserver_plus` (per the [Local Development Guide](../local-development.md)), you can run MinIO standalone:

```bash
cd backend
docker compose -f docker-compose.minio.yaml up -d
```

Then add to your `.env`:

```bash
# Enable file upload feature
WS_FILEHUB_FEATURE_ENABLED=true

# MinIO (R2 Emulator) - for local development
WS_FILEHUB_R2_ENDPOINT_URL=http://localhost:9000
WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL=http://localhost:9000
WS_FILEHUB_R2_ACCESS_KEY_ID=minioadmin
WS_FILEHUB_R2_SECRET_ACCESS_KEY=minioadmin
WS_FILEHUB_R2_BUCKET=ws-filehub-uploads
WS_FILEHUB_R2_WEBHOOK_ENABLED=false
```

## Configuration

MinIO uses sensible defaults but can be customized via environment variables (with defaults shown):

| Variable                 | Default              | Description             |
| ------------------------ | -------------------- | ----------------------- |
| `WS_MINIO_ROOT_USER`     | `minioadmin`         | MinIO admin username    |
| `WS_MINIO_ROOT_PASSWORD` | `minioadmin`         | MinIO admin password    |
| `WS_MINIO_API_PORT`      | `9000`               | S3 API port             |
| `WS_MINIO_CONSOLE_PORT`  | `9001`               | Web console port        |
| `WS_FILEHUB_R2_BUCKET`   | `ws-filehub-uploads` | Bucket for file uploads |

These are read from `.env-docker` when using `run-stack.sh --minio`, or can be set in the environment.

## Web Console

Access the MinIO web console at http://localhost:9001

- Username: `minioadmin` (or your `WS_MINIO_ROOT_USER`)
- Password: `minioadmin` (or your `WS_MINIO_ROOT_PASSWORD`)

From the console you can:

- Browse bucket contents
- Upload/download files manually
- Manage access policies
- Monitor storage usage

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Django App    │────▶│   MinIO (9000)  │
│  (filehub/r2)   │     │   S3-compatible │
└─────────────────┘     └─────────────────┘
         │                      │
         │                      │
         ▼                      ▼
┌─────────────────┐     ┌─────────────────┐
│   Browser       │────▶│  MinIO Console  │
│ (presigned URLs)│     │     (9001)      │
└─────────────────┘     └─────────────────┘
```

The setup creates two services:

1. **ws-minio**: The MinIO server (S3 API on port 9000, console on port 9001)
2. **ws-minio-init**: One-shot container that creates the bucket on startup

When used with `run-stack.sh --minio`, the compose file also injects R2 configuration into ws-web and ws-rq services.

## Troubleshooting

### Connection Refused

Ensure MinIO is running:

```bash
# Docker stack
docker compose -p <project-name> ps

# Standalone
docker compose -f docker-compose.minio.yaml ps
```

### Bucket Not Found

The init container creates the bucket automatically. If missing, check init logs:

```bash
docker compose -f docker-compose.minio.yaml logs ws-minio-init
```

Or create manually via console at http://localhost:9001.

### Presigned URL Issues

Ensure `WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL` matches how your browser accesses MinIO. For local development, this is typically `http://localhost:9000`.

## Limitations

- No R2 event notifications (webhook finalization won't work)
- Webhook is automatically disabled when using MinIO
- Use client-side finalization (`POST /api/files/{id}/finalize/`) instead
