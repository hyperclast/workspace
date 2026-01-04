/**
 * End-to-end tests for checking console errors during page load.
 *
 * Tests:
 * 1. No CodeMirror plugin crashes during editor lifecycle
 * 2. Track specific crash patterns for debugging
 *
 * Run with:
 *   npx playwright test console-errors.spec.js --headed
 *
 * Background:
 * A crash was observed in @codemirror/lang-markdown where the plugin tries to
 * access `.top` on a null element during the plugin update cycle. This test
 * tracks whether updates to @codemirror packages resolve the issue.
 *
 * Related packages (check for updates):
 * - @codemirror/lang-markdown
 * - @codemirror/view
 * - @codemirror/state
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
}

function categorizeError(errorText) {
  if (errorText.includes("CodeMirror plugin crashed")) {
    if (errorText.includes("can't access property") && errorText.includes("top")) {
      return "codemirror_markdown_top_null";
    }
    if (errorText.includes("md index.js") || errorText.includes("lang-markdown")) {
      return "codemirror_markdown_other";
    }
    return "codemirror_plugin_other";
  }
  if (errorText.includes("WebSocket")) {
    return "websocket";
  }
  return "other";
}

test.describe("CodeMirror Plugin Stability", () => {
  test.setTimeout(90000);

  test("editor initializes without plugin crashes", async ({ page }) => {
    const errors = {
      codemirror_markdown_top_null: [],
      codemirror_markdown_other: [],
      codemirror_plugin_other: [],
      websocket: [],
      other: [],
    };

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        const category = categorizeError(text);
        errors[category].push(text);
      }
    });

    page.on("pageerror", (error) => {
      errors.other.push(`Page Error: ${error.message}`);
    });

    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in and editor loaded");

    await page.waitForTimeout(2000);

    const newPageBtn = page.locator(".sidebar-new-page-btn").first();
    await newPageBtn.click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible({ timeout: 5000 });

    const titleInput = page.locator("#page-title-input");
    await titleInput.fill(`Plugin Test ${Date.now()}`);

    const createBtn = page.locator(".modal-btn-primary");
    await createBtn.click();

    await page.waitForSelector(".cm-content", { timeout: 10000 });
    await page.waitForTimeout(2000);
    console.log("✅ Created test page");

    const editor = page.locator(".cm-content");
    await editor.click();
    await page.keyboard.type("# Heading Test\n\n");
    await page.keyboard.type("- Bullet item\n");
    await page.keyboard.type("- [ ] Checkbox item\n\n");
    await page.keyboard.type("Some paragraph text here.\n\n");
    await page.keyboard.type("```javascript\nconst x = 1;\n```\n");
    await page.waitForTimeout(1000);
    console.log("✅ Added markdown content");

    console.log("\n📊 Error Summary:");
    console.log(`  - Markdown 'top' null errors: ${errors.codemirror_markdown_top_null.length}`);
    console.log(`  - Other markdown errors: ${errors.codemirror_markdown_other.length}`);
    console.log(`  - Other plugin errors: ${errors.codemirror_plugin_other.length}`);
    console.log(`  - WebSocket errors: ${errors.websocket.length}`);
    console.log(`  - Other errors: ${errors.other.length}`);

    if (errors.codemirror_markdown_top_null.length > 0) {
      console.log("\n🔴 Markdown 'top' null crash detected:");
      errors.codemirror_markdown_top_null.forEach((err, i) => {
        console.log(`  ${i + 1}. ${err.substring(0, 300)}...`);
      });
    }

    if (errors.codemirror_plugin_other.length > 0) {
      console.log("\n🔴 Other CodeMirror plugin crashes:");
      errors.codemirror_plugin_other.forEach((err, i) => {
        console.log(`  ${i + 1}. ${err.substring(0, 500)}`);
      });
    }

    if (errors.other.length > 0) {
      console.log("\n🔴 Other errors:");
      errors.other.forEach((err, i) => {
        console.log(`  ${i + 1}. ${err.substring(0, 300)}`);
      });
    }

    const totalPluginCrashes =
      errors.codemirror_markdown_top_null.length +
      errors.codemirror_markdown_other.length +
      errors.codemirror_plugin_other.length;

    expect(totalPluginCrashes).toBe(0);
    console.log("✅ No CodeMirror plugin crashes detected");
  });

  test("editor survives collaborative mode transition", async ({ page }) => {
    const errors = {
      during_init: [],
      during_collab: [],
      after_collab: [],
    };
    let phase = "during_init";

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (text.includes("CodeMirror plugin crashed")) {
          errors[phase].push(text);
        }
      }
      if (msg.type() === "log" && msg.text().includes("[Collab] Editor upgraded")) {
        phase = "after_collab";
      }
      if (msg.type() === "log" && msg.text().includes("collab_setup")) {
        phase = "during_collab";
      }
    });

    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    phase = "during_collab";
    console.log("✅ Logged in");

    await page.waitForTimeout(3000);
    phase = "after_collab";

    console.log("\n📊 Plugin Crash Timeline:");
    console.log(`  - During init: ${errors.during_init.length}`);
    console.log(`  - During collab setup: ${errors.during_collab.length}`);
    console.log(`  - After collab ready: ${errors.after_collab.length}`);

    if (errors.during_init.length > 0) {
      console.log("\n🔴 Crashes during init:");
      errors.during_init.forEach((err, i) => console.log(`  ${i + 1}. ${err.substring(0, 400)}`));
    }
    if (errors.during_collab.length > 0) {
      console.log("\n🔴 Crashes during collab setup:");
      errors.during_collab.forEach((err, i) => console.log(`  ${i + 1}. ${err.substring(0, 400)}`));
    }

    const totalCrashes =
      errors.during_init.length + errors.during_collab.length + errors.after_collab.length;

    expect(totalCrashes).toBe(0);
    console.log("✅ No plugin crashes during collaborative mode transition");
  });

  test("page reload stress test", async ({ page }) => {
    const crashesPerReload = [];

    page.on("console", (msg) => {
      if (msg.type() === "error" && msg.text().includes("CodeMirror plugin crashed")) {
        if (crashesPerReload.length > 0) {
          crashesPerReload[crashesPerReload.length - 1]++;
        }
      }
    });

    console.log(`\n🔧 Logging in as: ${TEST_EMAIL}`);
    await login(page);
    console.log("✅ Logged in");

    const RELOAD_COUNT = 5;
    for (let i = 0; i < RELOAD_COUNT; i++) {
      crashesPerReload.push(0);
      console.log(`\n🔄 Reload ${i + 1}/${RELOAD_COUNT}`);

      await page.reload();
      await page.waitForSelector(".cm-content", { timeout: 20000 });
      await page.waitForTimeout(2000);

      const editorReady = await page.evaluate(() => {
        return document.querySelector(".cm-editor") !== null;
      });
      console.log(`  Editor ready: ${editorReady}, Crashes: ${crashesPerReload[i]}`);
    }

    console.log("\n📊 Crashes per reload:", crashesPerReload);

    const totalCrashes = crashesPerReload.reduce((a, b) => a + b, 0);
    const avgCrashes = totalCrashes / RELOAD_COUNT;

    console.log(`📊 Total crashes: ${totalCrashes}`);
    console.log(`📊 Average crashes per reload: ${avgCrashes.toFixed(2)}`);

    expect(totalCrashes).toBe(0);
    console.log("✅ No plugin crashes during reload stress test");
  });
});
