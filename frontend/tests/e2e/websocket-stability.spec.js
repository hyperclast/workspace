/**
 * End-to-end test for WebSocket connection stability.
 *
 * This test monitors WebSocket connections for reconnection loops,
 * which indicate a problem with the collaboration layer.
 *
 * A healthy WebSocket connection should:
 * - Connect once
 * - Stay connected for the duration of the session
 * - NOT repeatedly connect/disconnect
 *
 * Run with:
 *   npm run test:websocket
 *
 * Or for headed mode (to see the browser):
 *   npm run test:websocket -- --headed
 *
 * To test with YOUR account:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npm run test:websocket -- --headed
 */

import { test, expect } from "@playwright/test";

// Configuration
const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";

// WebSocket stability thresholds
const OBSERVATION_PERIOD_MS = 10000; // 10 seconds observation period
const MAX_ACCEPTABLE_CONNECTIONS = 2; // Initial connect + maybe 1 reconnect is OK
const RECONNECT_LOOP_THRESHOLD = 3; // 3+ connections in observation period = problem

// Check if user provided existing credentials
const EXISTING_EMAIL = process.env.TEST_EMAIL;
const EXISTING_PASSWORD = process.env.TEST_PASSWORD;
const EXISTING_PAGE_ID = process.env.TEST_PAGE_ID;
const USE_EXISTING_ACCOUNT = EXISTING_EMAIL && EXISTING_PASSWORD;

// Generate unique test user credentials (only used if no existing account)
const TEST_USER_EMAIL = USE_EXISTING_ACCOUNT ? EXISTING_EMAIL : `wstest-${Date.now()}@example.com`;
const TEST_USER_PASSWORD = USE_EXISTING_ACCOUNT ? EXISTING_PASSWORD : "TestPassword123!";

test.describe("WebSocket Connection Stability", () => {
  let testPageId = EXISTING_PAGE_ID || "";
  let shouldCleanup = !USE_EXISTING_ACCOUNT;
  let csrfToken = "";

  test.beforeAll(async ({ browser }) => {
    if (USE_EXISTING_ACCOUNT) {
      console.log(`\n🔧 Using existing account: ${TEST_USER_EMAIL}`);
      if (EXISTING_PAGE_ID) {
        console.log(`   Testing page: ${EXISTING_PAGE_ID}`);
      }
      return;
    }

    console.log(`\n🔧 Setting up test user: ${TEST_USER_EMAIL}`);

    // Create a new browser context for setup
    const context = await browser.newContext();
    const page = await context.newPage();

    // Sign up via the UI
    await page.goto(`${BASE_URL}/signup`);
    await page.waitForSelector("#signup-email", { timeout: 10000 });

    await page.fill("#signup-email", TEST_USER_EMAIL);
    await page.fill("#signup-password", TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait for redirect to editor after signup
    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    console.log("✅ Test user created and logged in");

    // Get the current page ID
    const url = page.url();
    const pageMatch = url.match(/[?&]page=([^&]+)/);
    if (pageMatch) {
      testPageId = pageMatch[1];
    } else {
      testPageId = await page.evaluate(() => {
        return window.currentPage?.external_id || "";
      });
    }

    console.log(`✅ Test page ID: ${testPageId}`);

    // Get CSRF token for cleanup later
    csrfToken = await page.evaluate(() => window._csrfToken || "");

    await context.close();
  });

  test("WebSocket should not enter a reconnection loop", async ({ page }) => {
    // Track WebSocket connections
    const wsConnections = [];
    const wsDisconnections = [];

    // Listen to console messages for WebSocket status
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("WebSocket status:")) {
        const timestamp = Date.now();
        if (text.includes("connected")) {
          wsConnections.push(timestamp);
          console.log(`   🔌 WebSocket connected (${wsConnections.length})`);
        } else if (text.includes("disconnected")) {
          wsDisconnections.push(timestamp);
          console.log(`   ❌ WebSocket disconnected (${wsDisconnections.length})`);
        }
      }
      if (text.includes("Connecting to WebSocket:")) {
        console.log(`   🔄 ${text}`);
      }
    });

    // Listen to network requests for WebSocket connections
    const wsUrls = [];
    page.on("websocket", (ws) => {
      const url = ws.url();
      wsUrls.push({ url, timestamp: Date.now() });
      console.log(`   🌐 WebSocket opened: ${url}`);

      ws.on("close", () => {
        console.log(`   🔒 WebSocket closed: ${url}`);
      });

      ws.on("framereceived", () => {
        // We could log frame counts here if needed
      });
    });

    // Login first
    console.log("\n📋 Logging in...");
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_USER_EMAIL);
    await page.fill("#login-password", TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });

    // Navigate to the test page
    const targetUrl = testPageId ? `${BASE_URL}/pages/${testPageId}/` : `${BASE_URL}/`;

    console.log(`\n🚀 Navigating to: ${targetUrl}`);
    await page.goto(targetUrl);
    await page.waitForSelector(".cm-content", { timeout: 30000 });

    console.log(`\n⏱️  Observing WebSocket connections for ${OBSERVATION_PERIOD_MS / 1000}s...`);
    const observationStart = Date.now();

    // Wait and observe
    await page.waitForTimeout(OBSERVATION_PERIOD_MS);

    const observationEnd = Date.now();
    const totalObservationTime = observationEnd - observationStart;

    // Analyze results
    console.log("\n📊 WebSocket Stability Report:");
    console.log(`   Observation period: ${totalObservationTime}ms`);
    console.log(`   Total connections: ${wsConnections.length}`);
    console.log(`   Total disconnections: ${wsDisconnections.length}`);
    console.log(`   WebSocket URLs opened: ${wsUrls.length}`);

    // Calculate connection frequency
    if (wsConnections.length > 1) {
      const intervals = [];
      for (let i = 1; i < wsConnections.length; i++) {
        intervals.push(wsConnections[i] - wsConnections[i - 1]);
      }
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      console.log(`   Average reconnect interval: ${avgInterval.toFixed(0)}ms`);
    }

    // Determine if there's a reconnection loop
    const isReconnectLoop = wsConnections.length >= RECONNECT_LOOP_THRESHOLD;

    if (isReconnectLoop) {
      console.error(`\n❌ RECONNECTION LOOP DETECTED!`);
      console.error(`   ${wsConnections.length} connections in ${totalObservationTime}ms`);
      console.error(`   This indicates a problem with WebSocket stability.`);
      console.error(`\n   Possible causes:`);
      console.error(`   - Proxy/load balancer closing connections`);
      console.error(`   - y-websocket/pycrdt-websocket protocol mismatch`);
      console.error(`   - Server-side WebSocket timeout too short`);
      console.error(`   - Network instability`);
    } else if (wsConnections.length > MAX_ACCEPTABLE_CONNECTIONS) {
      console.warn(`\n⚠️  More connections than expected: ${wsConnections.length}`);
      console.warn(`   Not a critical loop, but worth investigating.`);
    } else {
      console.log(`\n✅ WebSocket connection is stable`);
    }

    // The test fails if we detect a reconnection loop
    expect(
      wsConnections.length,
      `WebSocket reconnection loop detected: ${wsConnections.length} connections in ${totalObservationTime}ms`
    ).toBeLessThan(RECONNECT_LOOP_THRESHOLD);
  });

  test("WebSocket connection should establish and receive sync", async ({ page }) => {
    let syncReceived = false;
    let connectionEstablished = false;

    // Listen for sync status messages
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("WebSocket status: connected")) {
        connectionEstablished = true;
      }
      if (text.includes("Sync status: synced")) {
        syncReceived = true;
      }
    });

    // Login
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_USER_EMAIL);
    await page.fill("#login-password", TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });

    // Navigate to page
    const targetUrl = testPageId ? `${BASE_URL}/pages/${testPageId}/` : `${BASE_URL}/`;

    await page.goto(targetUrl);
    await page.waitForSelector(".cm-content", { timeout: 30000 });

    // Wait for connection and sync (with timeout)
    const startTime = Date.now();
    const timeout = 5000; // 5 seconds should be plenty

    while (Date.now() - startTime < timeout) {
      if (connectionEstablished && syncReceived) {
        break;
      }
      await page.waitForTimeout(100);
    }

    console.log(`\n📊 Connection Test Results:`);
    console.log(`   Connection established: ${connectionEstablished ? "✅" : "❌"}`);
    console.log(`   Sync received: ${syncReceived ? "✅" : "❌"}`);
    console.log(`   Time taken: ${Date.now() - startTime}ms`);

    expect(connectionEstablished, "WebSocket should connect").toBe(true);
    expect(syncReceived, "Sync should complete").toBe(true);
  });

  test("extended stability test (30 seconds)", async ({ page }) => {
    // Longer observation for more confidence
    // Increase timeout for this specific test
    test.setTimeout(60000);
    const EXTENDED_OBSERVATION_MS = 30000;
    const wsEvents = [];

    // Track all WebSocket events
    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("WebSocket status:") || text.includes("Sync status:")) {
        wsEvents.push({
          timestamp: Date.now(),
          type: text.includes("connected")
            ? "connect"
            : text.includes("disconnected")
            ? "disconnect"
            : text.includes("synced")
            ? "sync"
            : "other",
          message: text,
        });
      }
    });

    // Login and navigate
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_USER_EMAIL);
    await page.fill("#login-password", TEST_USER_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForSelector("#editor", { timeout: 15000 });

    const targetUrl = testPageId ? `${BASE_URL}/pages/${testPageId}/` : `${BASE_URL}/`;

    console.log(`\n🚀 Starting extended stability test (${EXTENDED_OBSERVATION_MS / 1000}s)...`);
    await page.goto(targetUrl);
    await page.waitForSelector(".cm-content", { timeout: 30000 });

    // Extended observation
    await page.waitForTimeout(EXTENDED_OBSERVATION_MS);

    // Analyze events
    const connects = wsEvents.filter((e) => e.type === "connect");
    const disconnects = wsEvents.filter((e) => e.type === "disconnect");
    const syncs = wsEvents.filter((e) => e.type === "sync");

    console.log(`\n📊 Extended Stability Report:`);
    console.log(`   Duration: ${EXTENDED_OBSERVATION_MS / 1000}s`);
    console.log(`   Connects: ${connects.length}`);
    console.log(`   Disconnects: ${disconnects.length}`);
    console.log(`   Syncs: ${syncs.length}`);

    if (wsEvents.length > 0) {
      console.log(`\n   Event timeline:`);
      wsEvents.forEach((e, i) => {
        const relativeTime = i === 0 ? 0 : e.timestamp - wsEvents[0].timestamp;
        console.log(`   [${relativeTime}ms] ${e.type}: ${e.message}`);
      });
    }

    // In a healthy state, we should have 1 connect, 1 sync, and 0 disconnects
    // Allow for 1 reconnect scenario
    const isHealthy = connects.length <= 2 && disconnects.length <= 1;

    if (!isHealthy) {
      console.error(`\n❌ STABILITY ISSUE DETECTED`);
      console.error(`   Expected: ≤2 connects, ≤1 disconnect`);
      console.error(`   Got: ${connects.length} connects, ${disconnects.length} disconnects`);
    } else {
      console.log(`\n✅ Extended stability test passed`);
    }

    expect(connects.length, "Too many WebSocket connections").toBeLessThanOrEqual(2);
    expect(disconnects.length, "Unexpected disconnections").toBeLessThanOrEqual(1);
  });

  test.afterAll(async ({ request }) => {
    if (!shouldCleanup || !testPageId) {
      if (USE_EXISTING_ACCOUNT) {
        console.log(`\nℹ️  Existing account used - no cleanup needed`);
      }
      return;
    }

    // Cleanup: Delete the test page
    console.log(`\n🧹 Cleaning up test page: ${testPageId}`);
    try {
      const response = await request.delete(`${BASE_URL}/api/pages/${testPageId}/`, {
        headers: {
          "X-CSRFToken": csrfToken,
        },
      });
      if (response.ok()) {
        console.log("✅ Test page deleted");
      } else {
        console.warn(`⚠️  Could not delete test page: ${response.status()}`);
      }
    } catch (e) {
      console.warn("⚠️  Could not delete test page:", e.message);
    }
  });
});
