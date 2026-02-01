# Cloudflare R2 Setup for File Storage

Hyperclast uses Cloudflare R2 for file storage. This guide walks you through setting up R2 for your deployment.

## 1. Create an R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Go to **R2 Object Storage**
3. Click **Create bucket**
4. Set **Bucket name**: `hyperclast-ws-uploads` (or your preferred name)
5. Click **Create bucket**

## 2. Create an API Token

1. Go to **R2 Object Storage** in the dashboard
2. Click **Manage R2 API Tokens** → **Create API token**
3. Configure:
   - **Token name**: `hyperclast-backend`
   - **Permissions**: **Object Read & Write**
   - **Bucket(s)**: Select your bucket (e.g., `hyperclast-ws-uploads`)
4. Click **Create API Token**
5. **Save immediately** (shown only once):
   - Access Key ID
   - Secret Access Key
6. Note your **Account ID** from the dashboard URL (e.g., `https://dash.cloudflare.com/<account-id>/r2`)

## 3. Configure CORS

CORS must be configured to allow browser-based uploads.

1. Go to your bucket → **Settings** → **CORS Policy**
2. Add the following configuration:

```json
[
  {
    "AllowedOrigins": ["https://your-domain.com"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

**Notes:**

- Replace `https://your-domain.com` with your actual domain
- For development, you can use `["http://localhost:9800"]` or `["*"]`
- Restrict `AllowedOrigins` in production to your specific domain(s)

## 4. Configure Environment Variables

Add the following to your `backend/.env`:

```env
# Enable file upload feature
WS_FILEHUB_FEATURE_ENABLED=true

# R2 Storage Configuration
WS_FILEHUB_R2_ACCOUNT_ID=<your-account-id>
WS_FILEHUB_R2_ACCESS_KEY_ID=<access-key-id>
WS_FILEHUB_R2_SECRET_ACCESS_KEY=<secret-access-key>
WS_FILEHUB_R2_BUCKET=hyperclast-ws-uploads

# Primary upload target
WS_FILEHUB_PRIMARY_UPLOAD_TARGET=r2
```

### Environment Variables Reference

| Variable                            | Description                                 | Required |
| ----------------------------------- | ------------------------------------------- | -------- |
| `WS_FILEHUB_FEATURE_ENABLED`        | Enable file upload feature (`true`/`false`) | Yes      |
| `WS_FILEHUB_R2_ACCOUNT_ID`          | Your Cloudflare account ID                  | Yes      |
| `WS_FILEHUB_R2_ACCESS_KEY_ID`       | R2 API token access key                     | Yes      |
| `WS_FILEHUB_R2_SECRET_ACCESS_KEY`   | R2 API token secret key                     | Yes      |
| `WS_FILEHUB_R2_BUCKET`              | R2 bucket name                              | Yes      |
| `WS_FILEHUB_PRIMARY_UPLOAD_TARGET`  | Storage backend (`r2` or `local`)           | Yes      |
| `WS_FILEHUB_R2_ENDPOINT_URL`        | Custom S3 endpoint (for MinIO/dev)          | No       |
| `WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL` | Public endpoint for downloads               | No       |
| `WS_FILEHUB_REPLICATION_ENABLED`    | Enable multi-provider replication           | No       |

> **Note:** When `WS_FILEHUB_FEATURE_ENABLED=false`, the upload button is hidden and upload APIs return 503 Service Unavailable.

## 5. Local Development with MinIO (Optional)

For local development without Cloudflare R2, you can use MinIO as an S3-compatible alternative:

```env
WS_FILEHUB_PRIMARY_UPLOAD_TARGET=r2
WS_FILEHUB_R2_ACCOUNT_ID=minioadmin
WS_FILEHUB_R2_ACCESS_KEY_ID=minioadmin
WS_FILEHUB_R2_SECRET_ACCESS_KEY=minioadmin
WS_FILEHUB_R2_BUCKET=hyperclast-uploads
WS_FILEHUB_R2_ENDPOINT_URL=http://localhost:9000
WS_FILEHUB_R2_PUBLIC_ENDPOINT_URL=http://localhost:9000
```

Or use local filesystem storage:

```env
WS_FILEHUB_PRIMARY_UPLOAD_TARGET=local
```

## Troubleshooting

### CORS Errors

If you see CORS errors during file uploads:

1. Verify your CORS policy includes your origin
2. Ensure `AllowedMethods` includes `PUT` for uploads
3. Check that `AllowedHeaders` includes `*` or the specific headers your client sends

### Authentication Errors

If uploads fail with 403 errors:

1. Verify your API token has **Object Read & Write** permissions
2. Confirm the token is scoped to the correct bucket
3. Check that `WS_FILEHUB_R2_ACCESS_KEY_ID` and `WS_FILEHUB_R2_SECRET_ACCESS_KEY` are correct

## R2 Webhook Worker (Automatic Finalization)

For production deployments, you can set up automatic file upload finalization using R2 event notifications. This eliminates the need for clients to call the finalize endpoint after uploading.

### Why Use the Wrangler CLI

The webhook setup requires the [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/) because:

- **Queue creation**: Cloudflare Queues (used for R2 event notifications) can only be created via CLI
- **Event notifications**: R2 bucket event notifications must be configured via `wrangler r2 bucket notification` commands
- **Secret management**: Worker secrets are set via `wrangler secret put`
- **Deployment**: The worker is deployed using `wrangler deploy`

Install Wrangler with:

```bash
npm install -g wrangler
wrangler login
```

### Setup Documentation

- **Full setup guide**: [R2 Webhook Worker Setup](./r2-webhook-worker-setup.md) — step-by-step instructions for configuring queues, deploying the worker, and enabling event notifications
- **Worker overview**: [cloudflare/r2-webhook-worker/README.md](../../cloudflare/r2-webhook-worker/README.md) — quick start and development commands
