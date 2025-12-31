# Performance Monitoring & Testing

This document covers Hyperclast's performance monitoring infrastructure, including metrics collection, E2E tests, and optimization strategies.

## Architecture Overview

Hyperclast uses a two-phase page loading architecture to ensure instant content visibility:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PAGE LOAD TIMELINE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  0ms        100ms       200ms       500ms       1s          2s         5s   │
│  │           │           │           │          │           │          │    │
│  ▼           ▼           ▼           ▼          ▼           ▼          ▼    │
│  ┌───────────┐                                                              │
│  │ REST API  │ ← Content fetched from REST API                              │
│  └─────┬─────┘                                                              │
│        │                                                                    │
│        ▼                                                                    │
│  ┌───────────────────┐                                                      │
│  │ PHASE 1: RENDER   │ ← Content visible to user (no yCollab)              │
│  │ Editor + Content  │   Target: <500ms                                     │
│  └─────────┬─────────┘                                                      │
│            │                                                                │
│            │  ┌─────────────────────────────────────────────────────┐       │
│            └──│ PHASE 2: BACKGROUND COLLABORATION (async)           │       │
│               │                                                     │       │
│               │  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │       │
│               │  │ WS Connect │→ │ Yjs Sync   │→ │ Editor       │  │       │
│               │  │            │  │            │  │ Upgrade      │  │       │
│               │  └────────────┘  └────────────┘  └──────────────┘  │       │
│               │                                                     │       │
│               │  Target: <5s for collaboration ready                │       │
│               └─────────────────────────────────────────────────────┘       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why Two Phases?

1. **Phase 1 (Instant)**: Shows REST content immediately without waiting for WebSocket
2. **Phase 2 (Background)**: Upgrades to real-time collaboration without blocking

This ensures users see content in <500ms regardless of WebSocket connection speed.

## Metrics System

### Overview

The metrics system (`frontend/src/lib/metrics.js`) provides structured observability:

```javascript
import { metrics } from "./lib/metrics.js";

// Track a timed operation
const span = metrics.startSpan("operation_name", { key: "value" });
span.addEvent("milestone_reached", { details: 123 });
span.end({ status: "success" });

// Record a point-in-time event
metrics.event("user_action", { action: "click", target: "button" });

// Record an error
metrics.error("api_failure", error, { endpoint: "/api/pages/" });
```

### Console Output

Metrics are logged to the console with structured formatting:

```
[150ms] [page_load] ▶ Started {pageId: "abc123", contentLength: 1234}
[152ms] [page_load]   ├─ cleanup_complete (+2ms)
[155ms] [page_load]   ├─ setup_complete (+5ms)
[180ms] [page_load]   ├─ editor_init_complete (+30ms)
[182ms] [page_load] ◀ Completed in 32ms {status: "success"}
```

### Accessing Metrics in Browser

```javascript
// In browser console:
window.__metrics.getSummary(); // Aggregated statistics
window.__metrics.getRawData(); // All spans and events
window.__metrics.clear(); // Reset buffers
```

### Collected Spans

| Span Name         | Description                   | Threshold |
| ----------------- | ----------------------------- | --------- |
| `app_startup`     | Full app initialization       | -         |
| `page_navigation` | Click to content visible      | -         |
| `rest_fetch`      | REST API call duration        | 200ms     |
| `page_load`       | Time to first content visible | 500ms     |
| `collab_setup`    | WebSocket + sync + upgrade    | -         |
| `ws_sync`         | WebSocket sync only           | 2000ms    |
| `editor_upgrade`  | Adding yCollab extension      | 50ms      |

### Performance Thresholds

Operations exceeding thresholds are flagged as slow:

```javascript
const CONFIG = {
  slowThresholds: {
    page_load: 500, // Page should render in <500ms
    rest_fetch: 200, // REST API should respond in <200ms
    ws_connect: 1000, // WebSocket should connect in <1s
    ws_sync: 2000, // Sync should complete in <2s
    editor_init: 100, // Editor init should be <100ms
    editor_upgrade: 50, // Editor upgrade should be <50ms
  },
};
```

## E2E Performance Tests

### Running Tests

```bash
cd frontend

# Run all collaboration/performance tests
npm run test:collab

# Run in headed mode (see the browser)
npm run test:collab:headed

# Run specific test suite
npm run test:e2e -- tests/e2e/page-load-collab.spec.js --grep "Performance"

# Run with custom credentials
TEST_EMAIL=you@example.com TEST_PASSWORD=pass npm run test:collab
```

### Test Suites

#### Page Load Performance

Tests that content becomes visible within acceptable thresholds:

```javascript
test("content should be visible within threshold on initial load", async ({ page }) => {
  // Creates a page, navigates to it, measures time to content visibility
  // Asserts: visibleTime < 500ms
});

test("content should be visible within threshold on reload", async ({ page }) => {
  // Loads page, reloads, measures time to content visibility
  // Asserts: reloadTime < 500ms
});
```

#### Collaboration Sync

Tests the two-phase loading architecture:

```javascript
test("collaboration should connect after page is visible", async ({ page }) => {
  // Verifies content appears BEFORE collaboration connects
  // Ensures async upgrade doesn't block rendering
});

test("should handle sync timeout gracefully", async ({ page }) => {
  // Blocks WebSocket, verifies content still displays
  // Tests graceful degradation
});
```

#### Content Integrity

Critical tests to catch content duplication bugs:

```javascript
test("content should not duplicate on page load", async ({ page }) => {
  // Creates page with unique marker
  // Verifies marker appears exactly once after load + sync
});

test("content should not duplicate on reload", async ({ page }) => {
  // Same as above but after page reload
});

test("content should not duplicate on rapid navigation", async ({ page }) => {
  // Rapidly switches between pages
  // Verifies no content bleeding between pages
});
```

#### Edge Cases

```javascript
test("should handle empty page correctly");
test("should handle large content correctly"); // 100KB+
test("should handle special characters correctly"); // Unicode, emoji, code
```

### Test Output

Tests output detailed timing information:

```
📊 Content visible in: 145ms
📊 Metrics page_load duration: 142ms
📊 Collab connected 1234ms after content visible
📊 Marker occurrences: 1
✅ Content visible despite WebSocket being blocked
```

## Debugging Performance Issues

### 1. Check Browser Console

Look for metrics output:

```
[SLOW] [page_load] ◀ Completed in 1234ms ⚠️ SLOW (threshold: 500ms)
```

### 2. Get Detailed Breakdown

```javascript
// In browser console
const summary = window.__metrics.getSummary();
console.table(summary.stats);
```

Output:

```
┌─────────────────┬───────┬─────┬─────┬─────┬──────┬───────────┐
│ (index)         │ count │ min │ avg │ p95 │ max  │ slowCount │
├─────────────────┼───────┼─────┼─────┼─────┼──────┼───────────┤
│ page_load       │ 5     │ 89  │ 142 │ 230 │ 245  │ 0         │
│ rest_fetch      │ 5     │ 45  │ 78  │ 120 │ 125  │ 0         │
│ collab_setup    │ 5     │ 800 │ 1200│ 2100│ 2500 │ 1         │
└─────────────────┴───────┴─────┴─────┴─────┴──────┴───────────┘
```

### 3. Export Raw Data

```javascript
const data = window.__metrics.getRawData();
console.log(JSON.stringify(data, null, 2));
// Copy and analyze spans/events
```

### 4. Check Collaboration Status

Look for the status indicator in the UI:

- 🟢 Connected - Real-time collaboration active
- 🟡 Connecting - WebSocket connecting
- ⚪ Offline - Operating without real-time sync
- 🔴 Denied/Error - Access denied or connection failed

## Common Performance Issues

### Issue: Page takes >10s to load

**Symptom**: Content doesn't appear for 10+ seconds

**Cause**: WebSocket blocking page render (old architecture)

**Solution**: The two-phase architecture fixes this. Content now loads from REST API immediately.

### Issue: Content duplicates on reload

**Symptom**: Text appears twice after page reload

**Cause**: REST content inserted into ytext before sync, then server content merges

**Solution**:

1. Phase 1 renders without yCollab
2. Wait for sync to determine content source
3. Only then upgrade editor with yCollab

### Issue: WebSocket keeps reconnecting

**Symptom**: Status indicator cycles connecting → disconnected

**Cause**: Access denied but client keeps retrying

**Solution**: Frontend tracks denied pages and stops reconnection after 3 failures or specific close codes (4003, 4001, 1008)

## Future: Remote Telemetry

The metrics system is designed to support remote telemetry:

```javascript
// Future API (not yet implemented)
metrics.configure({
  remoteEndpoint: "/api/telemetry/",
  samplingRate: 0.1, // Send 10% of events
  batchSize: 50,
  flushInterval: 30000,
});
```

Planned features:

- Backend aggregation service
- Real-time dashboards (P50/P95/P99)
- Alerting on threshold violations
- Correlation with backend traces
- Historical trend analysis

## Related Documentation

- [E2E Testing Guide](e2e-testing.md) - General E2E test setup
- [CLAUDE.md](../CLAUDE.md) - Architecture overview
- [Collaboration Architecture](api/internal/crdt.md) - CRDT/Yjs details
