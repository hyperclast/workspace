# Local Development

For development without Docker.

## Backend

```sh
cd backend
cp .env-template .env   # then edit with your values
uv sync --group dev

# Required: generate an encryption key for API key storage
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add the output to WS_ENCRYPTION_KEY in .env
uv run pre-commit install
git config core.hooksPath backend/.githooks
uv run manage.py migrate
uv run manage.py runserver_plus 9800
```

Tests: `uv run manage.py test --parallel`

## Frontend

```sh
cd frontend
nvm use && npm install
npm run dev
```

Tests: `npm test`

## Running All Tests

```sh
./run-tests.sh                       # Full suite with dedicated Docker stack
./run-tests.sh --use-existing 9800   # Against running dev stack (faster)
./run-tests.sh --backend --frontend  # Skip E2E tests
```

See [E2E Testing Guide](e2e-testing.md) for more options.

## Performance Testing

```sh
cd frontend
npm run test:collab         # Run performance & collaboration tests
npm run test:collab:headed  # Run with visible browser
```

See [Performance Monitoring](performance.md) for metrics, debugging, and architecture details.

## AI Features

AI features (Ask, etc.) are enabled by default. Users configure their own API keys in Settings → AI. Supported providers:

- OpenAI
- Anthropic
- Google Gemini
- Custom (OpenAI-compatible endpoints)

To disable AI features, add to your `.env`:

```
WS_ASK_FEATURE_ENABLED=false
```

## File Uploads

File upload functionality is disabled by default. To enable it:

1. **Using MinIO (recommended for local dev):**

   ```sh
   ./run-stack.sh --minio 9800
   ```

   This automatically enables the feature via `docker-compose.minio.yaml`.

2. **Manual configuration:**
   Add to your `.env`:
   ```
   WS_FILEHUB_FEATURE_ENABLED=true
   ```
   Plus configure R2 or local storage. See `docs/cloudflare/` for R2 setup.

When disabled, the upload button is hidden and upload APIs return 503.
