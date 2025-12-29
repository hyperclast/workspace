# End-to-End (E2E) Testing

This document explains how to run E2E tests for Hyperclast, including WebSocket stability tests and page load time tests.

## Prerequisites

```bash
cd frontend
npm install
npx playwright install chromium
```

## Quick Reference

| Test                          | Command                          |
| ----------------------------- | -------------------------------- |
| WebSocket stability           | `npm run test:websocket`         |
| Page load time                | `npm run test:load-time`         |
| All E2E tests                 | `npm run test:e2e`               |
| Headed mode (visible browser) | Add `-- --headed` to any command |

## Testing Approaches

There are **two ways** to run E2E tests:

### Option 1: Test Against Your Running Dev Instance

This runs Playwright tests against your already-running Docker stack (port 9800). No new containers are started.

```bash
cd frontend

# Using a test account (creates new user automatically)
TEST_BASE_URL=http://localhost:9800 npm run test:websocket

# Using YOUR account (for debugging real issues)
TEST_EMAIL=you@example.com \
TEST_PASSWORD=yourpass \
TEST_BASE_URL=http://localhost:9800 \
npm run test:websocket -- --headed

# Test a specific page
TEST_EMAIL=you@example.com \
TEST_PASSWORD=yourpass \
TEST_PAGE_ID=abc123 \
TEST_BASE_URL=http://localhost:9800 \
npm run test:websocket -- --headed
```

**When to use**: Debugging issues on your current dev environment, testing with real data.

### Option 2: Spin Up a Dedicated Test Stack

This starts a **completely separate** Docker Compose stack that won't interfere with your dev instance:

- Different project name: `ws-e2e`
- Different port: `19800` (well away from common ports)
- Different database volume: `ws-e2e-db-data`
- Fresh database with test data

```bash
# Run all E2E tests
./scripts/run-e2e-tests.sh

# Run only WebSocket stability tests
./scripts/run-e2e-tests.sh websocket

# Run only load time tests
./scripts/run-e2e-tests.sh load-time

# Run with visible browser
./scripts/run-e2e-tests.sh websocket --headed

# Keep the test stack running after tests (for debugging)
./scripts/run-e2e-tests.sh --keep
```

**When to use**: CI/CD pipelines, clean-slate testing, avoiding interference with dev work.

## Available Tests

### WebSocket Stability Test

**File**: `frontend/tests/e2e/websocket-stability.spec.js`

Monitors WebSocket connections to detect reconnection loops. A healthy connection should:

- Connect once
- Stay connected for the session duration
- NOT repeatedly connect/disconnect

**What it checks**:

- Number of WebSocket connections over a 10-30 second period
- Connection/disconnection patterns
- Sync completion

**Failure indicates**:

- Proxy/load balancer issues
- y-websocket/pycrdt-websocket protocol mismatch
- Server-side WebSocket timeout too short
- Network instability

```bash
# Quick test (10 second observation)
npm run test:websocket

# With browser visible
npm run test:websocket -- --headed
```

### Page Load Time Test

**File**: `frontend/tests/e2e/note-load-time.spec.js`

Measures how long it takes from page load to content appearing in the editor.

**Thresholds**:

- ✅ Acceptable: < 1 second
- ⚠️ Warning: 1-3 seconds
- ❌ Failure: > 3 seconds

```bash
npm run test:load-time
```

## Environment Variables

| Variable         | Description                   | Default                   |
| ---------------- | ----------------------------- | ------------------------- |
| `TEST_BASE_URL`  | URL of the app to test        | `http://localhost:9800`   |
| `TEST_EMAIL`     | Use existing account email    | (creates new user)        |
| `TEST_PASSWORD`  | Use existing account password | (creates new user)        |
| `TEST_PAGE_ID`   | Test a specific page          | (uses any available page) |
| `E2E_KEEP_STACK` | Don't tear down test stack    | `0`                       |
| `E2E_NO_BUILD`   | Skip Docker image builds      | `0`                       |
| `E2E_HEADED`     | Run with visible browser      | `0`                       |

## Test Stack Architecture

When using `./scripts/run-e2e-tests.sh`, a separate Docker Compose stack is created:

```
Your Dev Stack (ws-*)          Test Stack (ws-e2e-*)
├── ws-db (port 5432)          ├── ws-e2e-db (internal)
├── ws-redis                   ├── ws-e2e-redis
├── ws-frontend                ├── ws-e2e-frontend
├── ws-web (port 9800)         ├── ws-e2e-web (port 19800)  ← Different port!
└── ws-rq                      └── ws-e2e-rq
```

The test stack uses:

- `backend/docker-compose.e2e.yaml` - Port overrides
- `backend/.env-e2e` - Separate environment (auto-created)

## Debugging Failed Tests

### WebSocket Reconnection Loop

If the WebSocket stability test fails with a reconnection loop:

1. **Check Docker logs**:

   ```bash
   docker compose -p ws-e2e logs ws-web --tail=100
   ```

2. **Common causes**:

   - Cloudflare/nginx WebSocket timeout too short
   - y-websocket library version mismatch
   - Server closing connections prematurely

3. **Debug with your account**:
   ```bash
   TEST_EMAIL=you@example.com \
   TEST_PASSWORD=yourpass \
   TEST_BASE_URL=http://localhost:9800 \
   npm run test:websocket -- --headed
   ```

### Slow Page Load

If the load time test fails:

1. Check the detailed timing breakdown in test output
2. Look for bottlenecks:
   - Editor visible but content delayed → WebSocket/CRDT issue
   - Editor slow to appear → Frontend bundle size
   - Everything slow → Backend/database issue

## Manual Cleanup

If the test stack doesn't clean up properly:

```bash
# Stop and remove test stack
docker compose -f backend/docker-compose.yaml -f backend/docker-compose.e2e.yaml \
  -p ws-e2e down -v --remove-orphans

# Remove test environment file
rm backend/.env-e2e
```

## CI/CD Integration

For CI pipelines, use the dedicated test stack:

```yaml
# Example GitHub Actions step
- name: Run E2E Tests
  run: |
    ./scripts/run-e2e-tests.sh
  env:
    E2E_NO_BUILD: 0 # Build images in CI
```

The script handles:

- Starting the stack
- Waiting for health checks
- Running migrations
- Executing tests
- Capturing logs
- Cleanup on exit
