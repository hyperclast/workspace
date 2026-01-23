# R2 Webhook Worker Setup Guide

This guide covers the production setup of the Cloudflare Worker that handles R2 event notifications for automatic file upload finalization.

## Architecture Overview

```
┌─────────────┐     ┌───────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Client    │────▶│  R2 Storage   │────▶│  Queue + Worker │────▶│   Backend   │
│  (Upload)   │     │  (PutObject)  │     │  (Forward Event)│     │  (Finalize) │
└─────────────┘     └───────────────┘     └─────────────────┘     └─────────────┘
```

1. **Client** uploads file directly to R2 using signed URL
2. **R2** emits event notification to a Queue
3. **Worker** consumes Queue, signs payload, forwards to backend
4. **Backend** verifies signature, finalizes the upload

## Prerequisites

- Cloudflare account with R2 enabled
- Wrangler CLI installed (`npm install -g wrangler`)
- Access to the Cloudflare dashboard

## Step 1: Create the Queue

Create a Queue to receive R2 event notifications:

```bash
wrangler queues create ws-r2-events
```

Create a dead letter queue for failed messages:

```bash
wrangler queues create ws-r2-events-dlq
```

## Step 2: Deploy the Worker

Navigate to the worker directory and deploy:

```bash
cd cloudflare/r2-webhook-worker
wrangler deploy
```

This deploys the worker that:

- Consumes events from the `ws-r2-events` queue
- Filters for relevant event types (create and delete)
- Signs payloads with HMAC-SHA256
- Forwards to the backend webhook endpoint

## Step 3: Configure Secrets

Set the required secrets for the worker:

```bash
# Backend webhook URL
wrangler secret put WEBHOOK_URL
# Enter: https://hyperclast.com/api/files/webhooks/r2-events/
# (or use the actual domain for your app, just make sure the path is `/api/files/webhooks/r2-events/`)

# Shared secret for HMAC signature (must match backend setting)
wrangler secret put WEBHOOK_SECRET
# Enter: <generated-secure-random-string>
```

**Important:** The `WEBHOOK_SECRET` must match the `WS_FILEHUB_R2_WEBHOOK_SECRET` environment variable in the backend.

## Step 4: Enable R2 Event Notifications

Enable event notifications on the R2 bucket:

```bash
# Enable object creation events
wrangler r2 bucket notification create ws-uploads \
  --event-type object-create \
  --queue ws-r2-events

# Enable object deletion events
wrangler r2 bucket notification create ws-uploads \
  --event-type object-delete \
  --queue ws-r2-events
```

Verify the configuration:

```bash
wrangler r2 bucket notification list ws-uploads
```

## Step 5: Configure Backend

Add these environment variables to the backend:

```bash
# Enable file upload feature
WS_FILEHUB_FEATURE_ENABLED=true

# Enable webhook processing
WS_FILEHUB_R2_WEBHOOK_ENABLED=true

# Shared secret (must match Worker's WEBHOOK_SECRET)
WS_FILEHUB_R2_WEBHOOK_SECRET=<same-secret-as-worker>
```

> **Note:** `WS_FILEHUB_FEATURE_ENABLED=true` must be set for file uploads to work. When disabled, the webhook endpoint returns 503.

## Verification

### Test the Worker

Use `wrangler tail` to monitor worker logs:

```bash
wrangler tail
```

Upload a file and verify you see:

1. "Received event: PutObject for users/..."
2. "Processed PutObject: users/..."

### Test End-to-End

1. Upload a test file via the frontend app
2. Check the file status - should be `available` without calling finalize

## Monitoring

### Worker Logs

```bash
wrangler tail
```

### Queue Metrics

View queue metrics in the Cloudflare dashboard:

- Messages received
- Messages acknowledged
- Messages in dead letter queue

### Backend Logs

Monitor backend logs for webhook events:

```
R2 webhook received: type=PutObject, bucket=ws-uploads, key=users/.../files/.../...
File upload finalized via webhook: <file_id>
```

## Troubleshooting

### Webhook Not Invoked

1. Check queue has messages: `wrangler queues info ws-r2-events`
2. Verify event notifications are enabled: `wrangler r2 bucket notification list ws-uploads`
3. Check worker logs: `wrangler tail`

### 401 Unauthorized

- Verify `WEBHOOK_SECRET` matches `WS_FILEHUB_R2_WEBHOOK_SECRET`
- Check signature is being computed correctly

### 400 Bad Request

- Verify `WS_FILEHUB_R2_WEBHOOK_ENABLED=true` in backend
- Check object key format matches expected pattern

### Rate Limiting (429)

The endpoint has rate limits:

- 60 requests/minute (burst)
- 10,000 requests/day

If hitting limits, check for:

- Duplicate events
- Retry storms

## Security Considerations

1. **Secret Management**: Store `WEBHOOK_SECRET` securely, rotate periodically
2. **HTTPS Only**: The worker only forwards to HTTPS endpoints
3. **Signature Verification**: Backend rejects requests without valid signatures
4. **Rate Limiting**: Protects backend from abuse

## Worker Configuration Reference

The `wrangler.toml` configuration:

```toml
name = "ws-r2-webhook-worker"
main = "src/index.js"
compatibility_date = "2024-12-01"

[[queues.consumers]]
queue = "ws-r2-events"
max_batch_size = 10
max_batch_timeout = 30
max_retries = 3
dead_letter_queue = "ws-r2-events-dlq"
```

Key settings:

- `max_batch_size`: Process up to 10 events at once
- `max_batch_timeout`: Wait up to 30 seconds to fill batch
- `max_retries`: Retry failed events 3 times before DLQ
