# Hyperclast

Collaborative workspace with real-time editing, bidirectional links, and AI-powered search.

![Hyperclast workspace](backend/core/static/core/img/app-screenshot-min.png)

- **Real-time collaboration**: Conflict-free sync via Yjs CRDT
- **Fast editor**: Built on CodeMirror 6
- **Bidirectional links**: Automatic backlinks between pages
- **AI search**: Query your workspace with RAG
- **Self-hostable**: ELv2 licensed

## Quick Start (Docker)

Create `backend/.env-docker`:

```sh
SECRET_KEY=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

cat << EOF > backend/.env-docker
WS_SECRET_KEY=${SECRET_KEY}
WS_ENCRYPTION_KEY=${ENCRYPTION_KEY}
WS_DB_USER=hyperclast
WS_DB_PASSWORD=hyperclast_pw
WS_DB_NAME=hyperclast
WS_ROOT_URL=http://localhost:9800
EOF
```

Run:

```sh
./run-stack.sh 9800           # Start stack (webapp at localhost:9800)
./restart-stack.sh backend    # Restart Django after code changes
./restart-stack.sh ls         # List running stacks
```

See `backend/.env-template` for all configuration options.

## Development

See [Local Development Guide](docs/local-development.md) for running without Docker.

### File Storage (Cloudflare R2)

File uploads are disabled by default. To enable, add to your `.env`:

```
WS_FILEHUB_FEATURE_ENABLED=true
WS_FILEHUB_PRIMARY_UPLOAD_TARGET=r2
WS_FILEHUB_R2_ACCOUNT_ID=<your-account-id>
WS_FILEHUB_R2_ACCESS_KEY_ID=<access-key-id>
WS_FILEHUB_R2_SECRET_ACCESS_KEY=<secret-access-key>
WS_FILEHUB_R2_BUCKET=hyperclast-ws-uploads
```

See [Cloudflare R2 Setup Guide](docs/cloudflare/r2-setup.md) for detailed instructions.

For local development, you can use MinIO as an R2 emulator:

```sh
./run-stack.sh --minio 9800
```

This starts all services plus MinIO with file uploads automatically enabled (S3 API on port 9000, console on port 9001). See [MinIO Local Setup](docs/cloudflare/minio-local-setup.md) for details.

### Data Import (Notion)

Import pages from Notion using their Markdown & CSV export:

1. Export from Notion: Settings → Export → Markdown & CSV
2. In Hyperclast, click the project menu (⋮) → "Import from Notion"
3. Upload the zip file

**Note:** Importing requires editor permissions on the project. Viewers cannot import.

Features:

- Automatic deduplication (re-importing skips existing pages)
- Internal link remapping to Hyperclast format
- Nested page flattening with original path preserved
- Zip bomb protection and archive security validation

See [Import System Documentation](docs/importing-data.md) for architecture details.

## License

The source code of this project is licensed under the **Elastic License v2
(ELv2)**. See [`LICENSE`](LICENSE) for details.

### What this means

- ✅ Free for individual use, learning, modification, and self-hosting
- ✅ Free for internal use within small teams
- ❌ You may NOT offer this software as a managed or hosted service
- ❌ You may NOT resell or repackage it as a competing service

If you are a business using this software beyond personal or evaluation use, you
must obtain a commercial license. See
[`COMMERCIAL_LICENSE`](COMMERCIAL_LICENSE.md) for details.
