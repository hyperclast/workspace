/**
 * End-to-end test for WebSocket connection stability.
 *
 * This test monitors WebSocket connections for reconnection loops,
 * which indicate a problem with the collaboration layer.
 *
 * Run with:
 *   npm run test:websocket
 *
 * Or for headed mode (to see the browser):
 *   npm run test:websocket -- --headed
 *
 * To test with a different account:
 *   TEST_EMAIL=you@example.com TEST_PASSWORD=yourpass npm run test:websocket -- --headed
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";

const OBSERVATION_PERIOD_MS = 10000;
const MAX_ACCEPTABLE_CONNECTIONS = 2;
const RECONNECT_LOOP_THRESHOLD = 3;

const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

test.describe("WebSocket Connection Stability", () => {
  test("WebSocket should not enter a reconnection loop", async ({ page }) => {
    const wsConnections = [];
    const wsDisconnections = [];

    page.on("console", (msg) => {
      const text = msg.text();
      if (text.includes("WebSocket status:")) {
        if (text.includes("connected")) {
          wsConnections.push(Date.now());
          console.log(`   🔌 WebSocket connected (${wsConnections.length})`);
        } else if (text.includes("disconnected")) {
          wsDisconnections.push(Date.now());
          console.log(`   ❌ WebSocket disconnected (${wsDisconnections.length})`);
        }
      }
      if (text.includes("Connecting to WebSocket:")) {
        console.log(`   🔄 ${text}`);
      }
    });

    const wsUrls = [];
    page.on("websocket", (ws) => {
      const url = ws.url();
      wsUrls.push({ url, timestamp: Date.now() });
      console.log(`   🌐 WebSocket opened: ${url}`);

      ws.on("close", () => {
        console.log(`   🔒 WebSocket closed: ${url}`);
      });
    });

    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Handle onboarding welcome page if it appears
    try {
      const welcomeBtn = page.locator('button:has-text("Get Started")');
      await welcomeBtn.waitFor({ timeout: 3000 });
      console.log("📝 Welcome page detected, completing onboarding...");
      await welcomeBtn.click();
    } catch {
      // No welcome page, continue
    }

    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });
    console.log("✅ Logged in");

    console.log(`\n⏱️  Observing WebSocket connections for ${OBSERVATION_PERIOD_MS / 1000}s...`);
    const observationStart = Date.now();

    await page.waitForTimeout(OBSERVATION_PERIOD_MS);

    const observationEnd = Date.now();
    const totalObservationTime = observationEnd - observationStart;

    console.log("\n📊 WebSocket Stability Report:");
    console.log(`   Observation period: ${totalObservationTime}ms`);
    console.log(`   Total connections: ${wsConnections.length}`);
    console.log(`   Total disconnections: ${wsDisconnections.length}`);
    console.log(`   WebSocket URLs opened: ${wsUrls.length}`);

    if (wsConnections.length > 1) {
      const intervals = [];
      for (let i = 1; i < wsConnections.length; i++) {
        intervals.push(wsConnections[i] - wsConnections[i - 1]);
      }
      const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
      console.log(`   Average reconnect interval: ${avgInterval.toFixed(0)}ms`);
    }

    const isReconnectLoop = wsConnections.length >= RECONNECT_LOOP_THRESHOLD;

    if (isReconnectLoop) {
      console.error(`\n❌ RECONNECTION LOOP DETECTED!`);
      console.error(`   ${wsConnections.length} connections in ${totalObservationTime}ms`);
    } else if (wsConnections.length > MAX_ACCEPTABLE_CONNECTIONS) {
      console.warn(`\n⚠️  More connections than expected: ${wsConnections.length}`);
    } else {
      console.log(`\n✅ WebSocket connection is stable`);
    }

    expect(
      wsConnections.length,
      `WebSocket reconnection loop detected: ${wsConnections.length} connections in ${totalObservationTime}ms`
    ).toBeLessThan(RECONNECT_LOOP_THRESHOLD);
  });

  test("WebSocket connection, sync, and 30-second stability", async ({ page }) => {
    test.setTimeout(60000);
    const EXTENDED_OBSERVATION_MS = 30000;
    const wsEvents = [];

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

    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait a moment for redirect
    await page.waitForTimeout(2000);

    // Debug: log current URL
    console.log(`📍 Current URL after login: ${page.url()}`);

    // Handle onboarding welcome page if it appears
    const welcomeBtn = page.locator(".onboarding-btn, button:has-text('Get Started')");
    const isWelcomePage = await welcomeBtn.isVisible().catch(() => false);
    if (isWelcomePage) {
      console.log("📝 Welcome page detected, completing onboarding...");
      await welcomeBtn.click();
      await page.waitForTimeout(2000);
      console.log(`📍 URL after onboarding: ${page.url()}`);
    }

    await page.waitForSelector("#editor", { timeout: 15000 });
    await page.waitForSelector(".cm-content", { timeout: 10000 });

    console.log(`\n🚀 Starting extended stability test (${EXTENDED_OBSERVATION_MS / 1000}s)...`);

    await page.waitForTimeout(EXTENDED_OBSERVATION_MS);

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

    // Verify connection happened
    expect(connects.length, "WebSocket should connect at least once").toBeGreaterThanOrEqual(1);

    // Verify sync happened
    expect(syncs.length, "WebSocket should sync at least once").toBeGreaterThanOrEqual(1);

    // Verify stability (no excessive reconnects)
    expect(connects.length, "Too many WebSocket connections").toBeLessThanOrEqual(2);
    expect(disconnects.length, "Unexpected disconnections").toBeLessThanOrEqual(1);

    console.log(`\n✅ WebSocket connection, sync, and stability verified`);
  });
});
