/**
 * Regression guard for the content-doubling bug: page content
 * doubled when two clients opened a seeded-but-empty-Yjs page in
 * parallel and the frontend gate inside `setupCollaborationAsync`
 * fired `ytext.insert(0, restContent)` on top of state the server
 * was about to deliver.
 *
 * Status on `master`:
 *   The fix is in. The frontend no longer inserts REST content
 *   into ytext at all; the server seeds `_seed_ydoc_from_page`
 *   under a per-room Postgres advisory transaction lock and is the
 *   single writer of the seed row. This spec exercises the
 *   end-to-end shape (rewind-restore → two parallel browsers →
 *   one row in `y_updates`) so a re-introduced race on a timescale
 *   Playwright can observe is caught.
 *
 *   Layered coverage:
 *   - `backend/collab/tests/websocket/test_content_duplication.py`
 *     pins the server-side guarantee (one row across two
 *     concurrent passive connects).
 *   - `frontend/src/tests/setup-collaboration-async.test.js` is
 *     the call-site canary against the original frontend
 *     regression (an inline `ytext.insert(0, restContent)`
 *     reappearing inside or near the post-sync branch).
 *   - This spec is the wider-window regression guard.
 *
 * Why E2E reproduction is unreliable:
 *   The bug's original mechanism was that `setupCollaborationAsync`
 *   resolved with `ytextHasContent=false` before SYNC_STEP2 from the
 *   server had been applied to the local ytext. That timing window
 *   lived inside the JS provider, not on the wire — Playwright's
 *   `routeWebSocket` can delay frames but cannot get between the
 *   "sync resolved" callback and a ytext mutation that a future
 *   regression might reintroduce. We use rewind-restore to put the
 *   room into the seeded-but-empty-Yjs state (since
 *   `pages/api/pages.py` auto-seeds Yjs after REST page creation,
 *   closing that path), and a small outbound-frame delay to widen
 *   the race, but neither is sufficient to fail this test
 *   deterministically against a re-introduced bug. The frontend
 *   vitest is the deterministic guard; this spec is belt-and-braces.
 *
 * Why rewind is the trigger we picked:
 *   `backend/pages/api/rewind.py` (the restore path) deletes every
 *   `y_updates` / `y_snapshots` row for the room and rewrites
 *   `Page.details["content"]`, with no follow-up seed task — the
 *   precondition the bug needs (Yjs storage empty,
 *   `details.content` non-empty). Creating a page via REST is
 *   closed by `_enqueue_yjs_sync_on_commit` in
 *   `pages/api/pages.py`.
 *
 * Run with:
 *   npm run test:e2e -- content-duplication.spec.js
 */

import { test, expect } from "@playwright/test";
import { waitForEditorContent } from "./helpers.js";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const SEED_CONTENT = "content1234";

// Long enough that both consumers complete `make_ydoc()` and the
// SYNC_STEP1 → SYNC_STEP2 round trip before either client's seed
// SYNC_UPDATE has been processed by the server. Short enough not
// to drag out the test wall-clock.
const WS_OUTBOUND_DELAY_MS = 500;

// Give the create-time `apply_text_update_to_page` task time to
// land before we wipe storage via rewind restore. Late writes
// after the wipe would re-populate `y_updates` and close the bug
// precondition.
const POST_CREATE_SETTLE_MS = 3000;

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 15000 });
  await page.waitForSelector(".cm-content", { timeout: 10000 });
}

async function createSeededPage(page, title, content) {
  return await page.evaluate(
    async ({ title, content }) => {
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];

      const projectsRes = await fetch("/api/projects/");
      const projects = await projectsRes.json();
      if (!projects.length) throw new Error("No projects available");
      const projectId = projects[0].external_id;

      const res = await fetch("/api/pages/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          project_id: projectId,
          title,
          details: { content, filetype: "txt", schema_version: 1 },
        }),
      });
      if (!res.ok) throw new Error(`createSeededPage failed: ${await res.text()}`);
      return await res.json();
    },
    { title, content }
  );
}

async function createRewindCheckpoint(page, pageId, label) {
  return await page.evaluate(
    async ({ id, lbl }) => {
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];

      const res = await fetch(`/api/pages/${id}/rewind/checkpoint/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ label: lbl }),
      });
      if (!res.ok) throw new Error(`createRewindCheckpoint failed: ${await res.text()}`);
      return await res.json();
    },
    { id: pageId, lbl: label }
  );
}

async function restoreRewind(page, pageId, rewindId) {
  return await page.evaluate(
    async ({ id, rid }) => {
      const csrfToken = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="))
        ?.split("=")[1];

      const res = await fetch(`/api/pages/${id}/rewind/${rid}/restore/`, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
      });
      if (!res.ok) throw new Error(`restoreRewind failed: ${await res.text()}`);
      return await res.json();
    },
    { id: pageId, rid: rewindId }
  );
}

async function deletePage(page, pageId) {
  await page.evaluate(async (id) => {
    const csrfToken = document.cookie
      .split("; ")
      .find((row) => row.startsWith("csrftoken="))
      ?.split("=")[1];
    await fetch(`/api/pages/${id}/`, {
      method: "DELETE",
      headers: { "X-CSRFToken": csrfToken },
    });
  }, pageId);
}

async function readEditorBody(page) {
  return await page.evaluate(() => window.editorView?.state?.doc?.toString() || "");
}

/**
 * Hold client→server WS frames for `delayMs` milliseconds. This
 * widens the make_ydoc-vs-seed-write race so both consumers are
 * guaranteed to reach their gate with empty `ytext` before either
 * client's SYNC_UPDATE writes to `y_updates`.
 */
async function installOutboundWsDelay(page, delayMs) {
  await page.routeWebSocket(/\/ws\//, (ws) => {
    const server = ws.connectToServer();
    ws.onMessage((msg) => {
      setTimeout(() => server.send(msg), delayMs);
    });
    server.onMessage((msg) => ws.send(msg));
  });
}

test.describe("Content doubling under concurrent open", () => {
  test("two collaborators opening a rewind-restored page in parallel do not double its content", async ({
    browser,
  }) => {
    // Setup context: creates the page and drives the rewind cycle
    // via the REST API. It never navigates to the page URL, so it
    // never holds an open WS to the room.
    const ctxSetup = await browser.newContext();
    const setupPage = await ctxSetup.newPage();
    await login(setupPage);

    const seeded = await createSeededPage(setupPage, `Dup Race ${Date.now()}`, SEED_CONTENT);
    const pageId = seeded.external_id;
    const pageUrl = `${BASE_URL}/pages/${pageId}/`;

    // Let the create-time `apply_text_update_to_page` task land
    // BEFORE we wipe `y_updates` via rewind. A late seed write
    // arriving after the wipe would re-populate Yjs and close the
    // bug's precondition.
    await setupPage.waitForTimeout(POST_CREATE_SETTLE_MS);

    // Snapshot the current content as a rewind, then restore it.
    // The restore deletes every `y_updates`/`y_snapshots` row for
    // the room and rewrites `Page.details["content"]` from the
    // rewind record (see pages/api/rewind.py:204-242). The room is
    // now in the seeded-but-empty-Yjs state the bug needs.
    const checkpoint = await createRewindCheckpoint(setupPage, pageId, "pre-race");
    await restoreRewind(setupPage, pageId, checkpoint.external_id);

    const ctxA = await browser.newContext();
    const ctxB = await browser.newContext();
    const pageA = await ctxA.newPage();
    const pageB = await ctxB.newPage();

    try {
      // Serial logins — parallel logins can collide on the shared
      // dev user's session. Parallelism that matters for this bug
      // is the page navigation, not the login.
      await login(pageA);
      await login(pageB);

      // Force the race: both contexts hold their outbound WS frames
      // long enough that both consumers' `make_ydoc()` runs against
      // empty `y_updates` before either client's seed SYNC_UPDATE
      // reaches the server. Without this delay the race is real
      // but flaky on localhost — too tight for a regression test.
      await installOutboundWsDelay(pageA, WS_OUTBOUND_DELAY_MS);
      await installOutboundWsDelay(pageB, WS_OUTBOUND_DELAY_MS);

      // Concurrent navigation — both clients must enter
      // setupCollaborationAsync before either has written its
      // seed update through the WebSocket.
      await Promise.all([pageA.goto(pageUrl), pageB.goto(pageUrl)]);

      // REST content appears immediately; collab upgrades later.
      await Promise.all([
        waitForEditorContent(pageA, SEED_CONTENT, 15000),
        waitForEditorContent(pageB, SEED_CONTENT, 15000),
      ]);

      // Allow collab to settle and the disconnect-snapshot path
      // plus `sync_snapshot_with_page` to rewrite
      // `Page.details["content"]` with whatever the CRDT resolved
      // to. 5 s is generous against the rq scheduler.
      await pageA.waitForTimeout(5000);

      // Reload both contexts so any in-memory editor state is
      // discarded and we observe what the backend now has.
      await Promise.all([pageA.reload(), pageB.reload()]);
      await Promise.all([
        waitForEditorContent(pageA, SEED_CONTENT, 15000),
        waitForEditorContent(pageB, SEED_CONTENT, 15000),
      ]);
      await pageA.waitForTimeout(2000);

      const bodyA = (await readEditorBody(pageA)).trim();
      const bodyB = (await readEditorBody(pageB)).trim();

      console.log(`[content-duplication] bodyA length=${bodyA.length}: ${bodyA}`);
      console.log(`[content-duplication] bodyB length=${bodyB.length}: ${bodyB}`);

      // On master both bodies are "content1234content1234". The
      // editor body must contain SEED_CONTENT exactly once and
      // nothing else.
      const occurrencesA = (bodyA.match(new RegExp(SEED_CONTENT, "g")) || []).length;
      const occurrencesB = (bodyB.match(new RegExp(SEED_CONTENT, "g")) || []).length;
      expect(occurrencesA).toBe(1);
      expect(occurrencesB).toBe(1);
      expect(bodyA).toBe(SEED_CONTENT);
      expect(bodyB).toBe(SEED_CONTENT);
    } finally {
      try {
        await deletePage(setupPage, pageId);
      } catch {
        // Best effort.
      }
      await ctxA.close();
      await ctxB.close();
      await ctxSetup.close();
    }
  });
});
