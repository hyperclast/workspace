/**
 * E2E test for MCP/REST live propagation into an open editor.
 *
 * Verifies the fix for the snapshot-drift bug: when an external caller
 * (MCP/REST) applies text to a page via `apply_text_to_room` while a
 * browser has the page open, the change must:
 *
 *   1. Appear LIVE in the editor (consumer forwards SYNC_UPDATE).
 *   2. SURVIVE a reload (consumer's self.ydoc was actually updated, so
 *      the disconnect snapshot contains the write).
 *
 * The reload check is the critical one — before the fix, step 1 passed
 * but step 2 silently failed because the snapshot was taken from a
 * self.ydoc that never saw the external update, while the watermark
 * still advanced past the update's y_updates row on disconnect.
 *
 * Run with:
 *   npm run test:e2e -- tests/e2e/mcp-live-propagation.spec.js
 *   npm run test:e2e -- tests/e2e/mcp-live-propagation.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import { dismissSocratesPanel, waitForEditorContent } from "./helpers.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";
const DOCKER_CONTAINER =
  process.env.TEST_DOCKER_CONTAINER || "backend-workspace-internal-9800-ws-web-1";

function isDockerContainerAvailable() {
  try {
    execSync(`docker inspect ${DOCKER_CONTAINER}`, {
      encoding: "utf-8",
      timeout: 5000,
      stdio: "pipe",
    });
    return true;
  } catch {
    return false;
  }
}

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await dismissSocratesPanel(page);
}

async function createEmptyPage(page, title) {
  // Capture URL BEFORE creating the page. After login, the user is redirected
  // to some pre-existing page (leftovers from previous runs), so the URL
  // already matches /pages/XXX/. Using `waitForURL` with a generic regex would
  // return immediately with the OLD pageId and we'd apply text to the wrong
  // room. Instead we wait for the URL to CHANGE off the pre-existing page.
  const preCreateUrl = page.url();

  const newPageBtn = page.locator(".sidebar-new-page-btn").first();
  await newPageBtn.click();

  const modal = page.locator(".modal");
  await modal.waitFor({ state: "visible", timeout: 5000 });
  await page.locator("#page-title-input").fill(title);
  await page.locator(".modal-btn-primary").click();

  await page.waitForSelector(".sidebar-item.active", { timeout: 10000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
  await page.waitForFunction(
    (prev) =>
      /\/pages\/[A-Za-z0-9]+\//.test(window.location.pathname) && window.location.href !== prev,
    preCreateUrl,
    { timeout: 10000 }
  );

  const pageId = page.url().match(/\/pages\/([A-Za-z0-9]+)\//)?.[1] || "";
  return pageId;
}

/**
 * Poll y_updates for a room until at least one row exists. Used to
 * confirm that the editor's WS writes have reached persistence before
 * we fire an external apply_text — otherwise apply_text reads from an
 * empty store and creates an update against a divergent base state,
 * breaking CRDT merge guarantees for the test assertions.
 */
function waitForPersistedUpdates(pageId, timeoutMs = 5000) {
  const script =
    "from collab.models import YUpdate; " +
    `print(YUpdate.objects.filter(room_id='page_${pageId}').count())`;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const out = execSync(
        `docker exec ${DOCKER_CONTAINER} python manage.py shell -c "${script}"`,
        { encoding: "utf-8", timeout: 10000, stdio: "pipe" }
      );
      const m = out.match(/^(\d+)\s*$/m);
      if (m && parseInt(m[1], 10) > 0) return;
    } catch {
      // ignore and retry
    }
  }
  throw new Error(`Baseline not persisted to y_updates for page ${pageId} within ${timeoutMs}ms`);
}

/**
 * Apply text to a page's Yjs doc directly via the backend service.
 *
 * This bypasses the MCP/REST HTTP layer and exercises exactly the path
 * the MCP tools ultimately invoke (apply_text_to_room). Using docker
 * exec keeps the test independent of MCP auth setup.
 *
 * Content is passed via env var to avoid shell-quoting headaches.
 */
function applyTextViaBackend(pageId, content, mode = "overwrite") {
  // `apply_text_to_room` now requires a user_id and re-checks can_edit_page.
  // Look up the dev user by email so the call runs as that authenticated
  // user (the same user whose browser session is driving the test).
  const script =
    "import os; " +
    "from django.contrib.auth import get_user_model; " +
    "from collab.services.apply_text import apply_text_to_room; " +
    "user = get_user_model().objects.get(email=os.environ['E2E_USER_EMAIL']); " +
    "result = apply_text_to_room(" +
    `'page_${pageId}', os.environ['E2E_CONTENT'], user.id, mode='${mode}'` +
    "); " +
    "print(result.name)";
  let result;
  try {
    result = execSync(
      `docker exec -e E2E_CONTENT -e E2E_USER_EMAIL ${DOCKER_CONTAINER} python manage.py shell -c "${script}"`,
      {
        encoding: "utf-8",
        timeout: 15000,
        env: { ...process.env, E2E_CONTENT: content, E2E_USER_EMAIL: TEST_EMAIL },
      }
    );
  } catch (err) {
    throw new Error(
      `docker exec failed (status=${err.status}): stdout=${err.stdout} stderr=${err.stderr}`
    );
  }
  console.log(`[applyTextViaBackend] stdout: ${result.trim()}`);
  if (!result.includes("APPLIED") && !result.includes("NOOP") && !result.includes("DENIED")) {
    throw new Error(`apply_text_to_room unexpected output: ${result}`);
  }
  return result.includes("APPLIED");
}

test.describe("MCP/REST live propagation into open editor", () => {
  test.setTimeout(120000);

  test("external write propagates live AND survives reload", async ({ page }) => {
    test.skip(!isDockerContainerAvailable(), `Docker container ${DOCKER_CONTAINER} not found`);

    await login(page);

    const title = `MCP Live ${Date.now()}`;
    const pageId = await createEmptyPage(page, title);
    expect(pageId).toBeTruthy();

    // Ensure the WS connection has settled before injecting the external
    // write — otherwise the broadcast can race the consumer's initial
    // sync handshake and the client may not see it live.
    await page.waitForFunction(
      () => {
        const indicator = document.getElementById("collab-status");
        return indicator && indicator.className.includes("connected");
      },
      { timeout: 15000 }
    );

    const externalContent = `Injected by MCP at ${Date.now()}: the quick brown fox`;
    const applied = applyTextViaBackend(pageId, externalContent, "overwrite");
    expect(applied).toBe(true);

    // Phase 1: change must appear LIVE in the editor.
    await waitForEditorContent(page, externalContent, 10000);

    // Phase 2: the critical drift check. Reload the page. The client's
    // Yjs state is thrown away; the editor will rehydrate from
    // y_snapshots + y_updates. Before the fix, the disconnect snapshot
    // would have been taken from a server-side self.ydoc that never saw
    // the injected update, and the watermark would have advanced past
    // the update's row — so the reload would show an empty doc.
    await page.reload();
    await page.waitForSelector(".cm-content", { timeout: 15000 });
    await dismissSocratesPanel(page);

    // Give hydration a moment to complete (REST fast-path then WS sync).
    await waitForEditorContent(page, externalContent, 15000);

    const finalContent = await page.evaluate(() => window.editorView?.state?.doc?.toString() || "");
    expect(finalContent).toContain(externalContent);
  });

  test("append mode propagates live AND survives reload", async ({ page }) => {
    test.skip(!isDockerContainerAvailable(), `Docker container ${DOCKER_CONTAINER} not found`);

    await login(page);

    const title = `MCP Append ${Date.now()}`;
    const pageId = await createEmptyPage(page, title);
    expect(pageId).toBeTruthy();

    // Ensure WS is connected BEFORE typing so the baseline edits are
    // sent through the normal SYNC_UPDATE path (not buffered pre-connect).
    await page.waitForFunction(
      () => {
        const indicator = document.getElementById("collab-status");
        return indicator && indicator.className.includes("connected");
      },
      { timeout: 15000 }
    );

    // Seed some baseline content by typing in the editor, so we have
    // something to append to.
    await page.click(".cm-content");
    await page.keyboard.type("Baseline content.");
    await waitForEditorContent(page, "Baseline content.");

    // Wait until the baseline has actually persisted to y_updates —
    // otherwise apply_text below would hydrate from an empty store and
    // its captured update would be based on a divergent state.
    waitForPersistedUpdates(pageId, 8000);

    const appendText = ` Appended by MCP at ${Date.now()}.`;
    applyTextViaBackend(pageId, appendText, "append");

    // Live: editor should contain both baseline and appended text.
    await waitForEditorContent(page, appendText, 10000);
    const afterLive = await page.evaluate(() => window.editorView?.state?.doc?.toString() || "");
    expect(afterLive).toContain("Baseline content.");
    expect(afterLive).toContain(appendText);

    // Reload and confirm both halves survive.
    await page.reload();
    await page.waitForSelector(".cm-content", { timeout: 15000 });
    await dismissSocratesPanel(page);
    await waitForEditorContent(page, appendText, 15000);

    const afterReload = await page.evaluate(() => window.editorView?.state?.doc?.toString() || "");
    expect(afterReload).toContain("Baseline content.");
    expect(afterReload).toContain(appendText);
  });
});
