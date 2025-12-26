# Hyperclast

Hyperclast Collaborative Workspace: Fast, Open, Extensible

## Highlights

- **Real-time collaboration** : Multiple users edit simultaneously with conflict-free sync (Yjs CRDT)
- **Lightning-fast editor** : Built on CodeMirror 6 for instant, responsive editing
- **Rich Markdown** : Tables, code blocks, checklists, and formatting with live preview
- **Bidirectional links** : Connect pages with links and automatic backlinks
- **AI-powered search** : Ask questions across your workspace with RAG-based retrieval
- **Self-hostable** : Easily run on your own infrastructure
- **Open source** : ELv2 licensed, free for personal and small team use

## Run Entire Stack

You can run the full stack (web app, RQ workers, Postgres, Redis, and frontend SPA with a single docker compose setup.

First, run the following command to create `.env-docker` (then replace with correct values):

```sh
cat << 'EOF' > .env-docker
WS_SECRET_KEY=change_this_secret_key
WS_DB_USER=hyperclast
WS_DB_PASSWORD=hyperclast_pw
WS_DB_NAME=hyperclast
WS_WEB_EXTERNAL_PORT=9800
WS_ROOT_URL=http://localhost:9800
EOF
```

Those are the minimum env vars to be set. See `.env-template` for the full list.

Once the env vars are set in the `.env-docker` file, you can now run the full stack:

```sh
./run-stack.sh
```

The app can now be accessed through `WS_ROOT_URL`.

## Backend Dev

## Environment Variables

All env vars are set/unset in the file `backend/.env`.  See `backend/.env-template` for an illustrative example.

### Postgres

1. Create the db and the db user
2. Provide the db-related values to the `WS_DB_*` env vars of the `backend/.env` file:

```
WS_DB_HOST=127.0.0.1
WS_DB_PORT=5432
WS_DB_USER=hyperclast
WS_DB_PASSWORD=hyperclast
WS_DB_NAME=hyperclast
```

### pgvector extension

Install pgvector extension:

```sh
sudo apt install postgresql-17-pgvector
```

Run the following as a superuser in the db:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Backend Setup

1. `cd backend`
2. Provide a value for the env var `WS_SECRET_KEY` in `backend/.env`
3. `uv sync --group dev`
4. `uv run pre-commit install`
5. `uv run manage.py migrate`

### Tests

```sh
uv run manage.py test --parallel
```

### Running Local Server

```sh
uv run manage.py runserver_plus <PORT>
```

## FrontEnd Dev

### Tests

```sh
cd frontend
npm test
```

**Performance Tests**: Run performance tests in two modes:

- **Default mode** (fast): `npm test -- src/tests/yjs-performance.test.js src/tests/codemirror-performance.test.js --run`
- **Full mode** (thorough testing): `PERF_FULL=1 npm test -- src/tests/yjs-performance.test.js src/tests/codemirror-performance.test.js --run`

Full mode uses larger datasets and stricter thresholds to catch performance regressions.

**E2E Tests**: See [E2E Testing Guide](docs/e2e-testing.md) for comprehensive documentation on:
- WebSocket stability tests (detect reconnection loops)
- Page load time tests (catch performance regressions)
- Running against your dev instance vs. a dedicated test stack

Quick start:
```sh
# Install Playwright (first time only)
cd frontend
npm install
npx playwright install chromium

# Run WebSocket stability test
npm run test:websocket

# Run load time test
npm run test:load-time

# Run with visible browser
npm run test:websocket -- --headed
```

### Run
```sh
cd frontend
nvm use
npm install
npm run dev
```

## Ask Feature

We use RAG to implement the Ask feature. This allows users to query, search, and extract info from their pages.

To enable the feature, make sure to set the following env vars:

```
WS_ASK_FEATURE_ENABLED=true
WS_OPENAI_API_KEY=<openai-api-key>
```

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
