# R2 Webhook Worker

Cloudflare Worker that consumes R2 event notifications and forwards them to the backend webhook endpoint for automatic file upload finalization.

## Overview

This worker:

- Consumes R2 bucket event notifications from a Cloudflare Queue
- Filters for relevant events (object create/delete)
- Signs payloads with HMAC-SHA256
- Forwards to the backend webhook endpoint

For detailed setup instructions, see the [R2 Webhook Worker Setup Guide](../../docs/cloudflare/r2-webhook-worker-setup.md).

## Quick Start

```bash
# Install dependencies
npm install -g wrangler
wrangler login

# Deploy
wrangler deploy

# Set secrets
wrangler secret put WEBHOOK_URL    # Backend webhook endpoint
wrangler secret put WEBHOOK_SECRET # Shared HMAC secret
```

## Development

```bash
# View logs
wrangler tail

# Check deployments
wrangler deployments list
```

## Configuration

See `wrangler.toml` for queue consumer configuration.

Required secrets:

- `WEBHOOK_URL`: Backend webhook endpoint (e.g., `https://api.hyperclast.com/api/files/webhooks/r2-events/`)
- `WEBHOOK_SECRET`: Shared secret for HMAC signature verification
