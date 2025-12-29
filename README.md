# Hyperclast

Collaborative workspace with real-time editing, bidirectional links, and AI-powered search.

- **Real-time collaboration**: Conflict-free sync via Yjs CRDT
- **Fast editor**: Built on CodeMirror 6
- **Bidirectional links**: Automatic backlinks between pages
- **AI search**: Query your workspace with RAG
- **Self-hostable**: ELv2 licensed

## Quick Start (Docker)

Create `backend/.env-docker`:

```sh
cat << 'EOF' > backend/.env-docker
WS_SECRET_KEY=change_this_secret_key
WS_DB_USER=hyperclast
WS_DB_PASSWORD=hyperclast_pw
WS_DB_NAME=hyperclast
WS_ROOT_URL=http://localhost:9800
EOF
```

Run:

```sh
./run-stack.sh          # port 9800
./run-stack.sh 9810     # alternate port
```

See `backend/.env-template` for all options.

## Local Development

### Backend

```sh
cd backend
cp .env-template .env   # then edit with your values
uv sync --group dev
uv run pre-commit install
git config core.hooksPath backend/.githooks
uv run manage.py migrate
uv run manage.py runserver_plus 9800
```

Tests: `uv run manage.py test --parallel`

### Frontend

```sh
cd frontend
nvm use && npm install
npm run dev
```

Tests: `npm test`

E2E tests: See [E2E Testing Guide](docs/e2e-testing.md)

### AI Search (Optional)

Add to your `.env`:

```
WS_ASK_FEATURE_ENABLED=true
WS_OPENAI_API_KEY=<your-key>
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
