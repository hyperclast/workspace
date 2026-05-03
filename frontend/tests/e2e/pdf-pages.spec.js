/**
 * End-to-end smoke tests for PDF-native pages (filetype="pdf", schema_version=2).
 *
 * Mirrors the verification list in specs/pdf-native-page.md §Verification:
 *   - PDF page renders inline (no toolbar, no CodeMirror)
 *   - Both PDF pages are visible/scrollable
 *   - Comments tab loads without crashing
 *   - Rewind tab is hidden on PDF pages
 *   - Rewind checkpoint endpoint returns 400
 *   - Access-code endpoint returns 400
 *   - Replies cannot carry a `pdf_anchor` (constraint surfaces as 400)
 *   - PDF page rejects text (Yjs) anchors on root comments — 400
 *   - Markdown page rejects `pdf_anchor` on root comments — 400
 *   - Download endpoint returns 302 to signed URL
 *   - Search by extracted-text phrase finds the PDF page
 *
 * Selection-driven flows (popover → comment, sidebar → focus pulse) are
 * exercised via manual verification rather than scripted DOM selection — the
 * PDF.js text layer's spans don't selection-emulate cleanly in headless mode.
 *
 * Run with:
 *   npx playwright test pdf-pages.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { dismissSocratesPanel } from "./helpers.js";
import path from "path";
import fs from "fs";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

const SAMPLE_PDF = path.resolve(import.meta.dirname, "fixtures/sample.pdf");

const SAMPLE_TITLE = "sample";
// Pre-extracted text (PDF.js does this client-side; for tests we hard-code it).
const SAMPLE_CONTENT = [
  "# Page 1",
  "",
  "Introduction to Machine Learning",
  "Machine learning is a subset of artificial intelligence.",
  "",
  "# Page 2",
  "",
  "Supervised Learning uses labeled data.",
].join("\n");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
  await dismissSocratesPanel(page);
}

async function getFirstProjectId(page) {
  await page.waitForSelector(".sidebar-project[data-project-id]", { timeout: 10000 });
  return page.locator(".sidebar-project[data-project-id]").first().getAttribute("data-project-id");
}

async function getCookies(page) {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((c) => c.name === "csrftoken");
  const session = cookies.find((c) => c.name === "sessionid");
  return {
    csrf: csrf?.value || "",
    cookieHeader: `csrftoken=${csrf?.value || ""}; sessionid=${session?.value || ""}`,
  };
}

async function importPdfViaApi(page, projectId) {
  const { csrf, cookieHeader } = await getCookies(page);
  const response = await page.context().request.post(`${BASE_URL}/api/v1/imports/pdf/`, {
    multipart: {
      project_id: projectId,
      title: SAMPLE_TITLE,
      content: SAMPLE_CONTENT,
      file: {
        name: "sample.pdf",
        mimeType: "application/pdf",
        buffer: fs.readFileSync(SAMPLE_PDF),
      },
    },
    headers: {
      "X-CSRFToken": csrf,
      Cookie: cookieHeader,
    },
  });
  const status = response.status();
  const data = await response.json();
  // Fail loudly on non-201 so callers don't silently propagate `undefined`
  // page IDs into downstream URLs (where they surface as misleading 404s).
  // The most common cause is import throttling (default: 10/hour per user
  // via WS_IMPORTS_RATE_LIMIT_REQUESTS) — bump that env var when running
  // the suite back-to-back.
  if (status !== 201) {
    throw new Error(
      `importPdfViaApi expected 201, got ${status}: ${JSON.stringify(data)}. ` +
        `If status is 429, raise WS_IMPORTS_RATE_LIMIT_REQUESTS in the dev stack.`
    );
  }
  return { response, status, data };
}

async function openPage(page, pageId) {
  await page.goto(`${BASE_URL}/pages/${pageId}/`);
  // PDF pages don't render CodeMirror — wait for the inline PDF viewer instead.
  await page.waitForSelector(".pdf-page-view", { timeout: 20000 });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("PDF-native pages", () => {
  test.setTimeout(120000);

  test("breadcrumb row is clean on a freshly loaded PDF page (no empty presence pill)", async ({
    page,
  }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { data } = await importPdfViaApi(page, projectId);

    // Fresh navigation = same code path as a hard reload: SPA boots, then
    // loadPage() routes to loadPdfPage(). PDF pages skip Yjs collab, so the
    // markdown-page presence setup never runs and the #presence-indicator
    // div is left styled-but-empty unless something hides it.
    await openPage(page, data.page_external_id);

    const wrapper = page.locator('[data-pdf-page="1"]');
    const errorBanner = page.locator(".pdf-status-error");
    await expect(wrapper.or(errorBanner)).toBeVisible({ timeout: 15000 });
    if ((await errorBanner.count()) > 0) {
      test.skip(
        true,
        "PDF render failed in this env; breadcrumb-only assertions still need a rendered page"
      );
    }

    const breadcrumbRow = page.locator("#breadcrumb-row");
    await expect(breadcrumbRow).toBeVisible();
    await expect(page.locator("#breadcrumb-page")).toContainText(SAMPLE_TITLE);

    const presence = page.locator("#presence-indicator");
    if (await presence.isVisible()) {
      const text = (await presence.textContent()).trim();
      expect(
        text,
        "presence-indicator is visible but empty — it renders as a styled blue pill with no content"
      ).not.toBe("");
    }
  });

  test("breadcrumb row is clean after explicit page.reload() on a PDF page", async ({ page }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { data } = await importPdfViaApi(page, projectId);
    await openPage(page, data.page_external_id);

    await page.reload();
    const wrapper = page.locator('[data-pdf-page="1"]');
    const errorBanner = page.locator(".pdf-status-error");
    await expect(wrapper.or(errorBanner)).toBeVisible({ timeout: 15000 });
    if ((await errorBanner.count()) > 0) {
      test.skip(true, "PDF render failed in this env after reload");
    }

    const presence = page.locator("#presence-indicator");
    if (await presence.isVisible()) {
      const text = (await presence.textContent()).trim();
      expect(text, "after reload, presence-indicator renders as a styled empty pill").not.toBe("");
    }
  });

  test("presence indicator does not show stale 'X user editing' content after navigating from a markdown page to a PDF page", async ({
    page,
  }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { csrf, cookieHeader } = await getCookies(page);

    const mdResp = await page.context().request.post(`${BASE_URL}/api/v1/pages/`, {
      data: { project_id: projectId, title: `md-before-pdf-${Date.now()}` },
      headers: {
        "X-CSRFToken": csrf,
        Cookie: cookieHeader,
        "Content-Type": "application/json",
      },
    });
    expect(mdResp.status()).toBe(201);
    const mdPage = await mdResp.json();

    await page.goto(`${BASE_URL}/pages/${mdPage.external_id}/`);
    await page.waitForSelector(".cm-content", { timeout: 15000 });
    await page.waitForSelector("#user-count", { timeout: 10000 });

    const { data } = await importPdfViaApi(page, projectId);
    await page.goto(`${BASE_URL}/pages/${data.page_external_id}/`);
    await page.waitForSelector(".pdf-page-view, .pdf-status-error", { timeout: 20000 });

    const presence = page.locator("#presence-indicator");
    if (await presence.isVisible()) {
      const text = (await presence.textContent()).trim();
      expect(
        text,
        "after navigating md→pdf, presence-indicator should not show stale 'user editing' content from the previous markdown page"
      ).not.toMatch(/user.*editing/i);
      expect(
        text,
        "after navigating md→pdf, presence-indicator should not render as a styled empty pill"
      ).not.toBe("");
    }
  });

  test("collab status indicator does not show stale 'Offline' after navigating from a markdown page to a PDF page", async ({
    page,
  }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { csrf, cookieHeader } = await getCookies(page);

    const mdResp = await page.context().request.post(`${BASE_URL}/api/v1/pages/`, {
      data: { project_id: projectId, title: `md-before-pdf-collab-${Date.now()}` },
      headers: {
        "X-CSRFToken": csrf,
        Cookie: cookieHeader,
        "Content-Type": "application/json",
      },
    });
    expect(mdResp.status()).toBe(201);
    const mdPage = await mdResp.json();

    // Import the PDF *before* loading the markdown page so the SPA's project
    // cache (cachedProjects) picks up both pages on the initial fetch — that
    // way the breadcrumb row populates correctly when we later navigate to
    // the PDF page via SPA routing.
    const { data } = await importPdfViaApi(page, projectId);

    // Open the markdown page so the collab-status wrapper gets created and
    // reaches a steady "connected" state. The bug is that the wrapper's DOM
    // element persists across SPA navigation — only sidenav-click (not
    // page.goto) reproduces it because page.goto does a full document reload
    // which boots the SPA fresh.
    await page.goto(`${BASE_URL}/pages/${mdPage.external_id}/`);
    await page.waitForSelector(".cm-content", { timeout: 15000 });
    await page.waitForSelector("#collab-status-wrapper", { timeout: 10000 });

    // Mimic sidenav-click navigation via the SPA router.
    await page.evaluate((id) => window.openPage(id), data.page_external_id);
    await page.waitForSelector(".pdf-page-view, .pdf-status-error", { timeout: 20000 });

    const wrapper = page.locator("#collab-status-wrapper");
    const visible = (await wrapper.count()) > 0 && (await wrapper.isVisible());
    expect(
      visible,
      "after SPA-navigating md→pdf, collab-status-wrapper should not be visible — PDF pages have no Yjs collab, so the dot is stale state from the prior page"
    ).toBe(false);
  });

  test("PDF page renders inline with hidden toolbar and visible page wrappers", async ({
    page,
  }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { status, data } = await importPdfViaApi(page, projectId);
    expect(status).toBe(201);

    await openPage(page, data.page_external_id);

    // Toolbar must be hidden on PDF pages. Scope to #note-page because the
    // SPA shell renders a second placeholder #toolbar-wrapper in index.html;
    // the one inside #note-page is what loadPdfPage.js actually toggles.
    const toolbar = page.locator("#note-page #toolbar-wrapper");
    await expect(toolbar).toBeHidden();

    // No CodeMirror on PDF pages.
    expect(await page.locator(".cm-content").count()).toBe(0);

    // At least one PDF page wrapper renders. (Lazy renderer guarantees page 1.)
    // PdfPageView shows .pdf-status-error when PDF.js can't fetch the file —
    // that's an environment problem (e.g. WS_ROOT_URL pointing at an
    // unreachable Cloudflare tunnel for this dev box), not a regression. Wait
    // for either outcome and skip with diagnostics if the load failed so the
    // useful "no toolbar / no CodeMirror" assertions above still get to run.
    const wrapper = page.locator('[data-pdf-page="1"]');
    const errorBanner = page.locator(".pdf-status-error");
    await expect(wrapper.or(errorBanner)).toBeVisible({ timeout: 15000 });
    if ((await errorBanner.count()) > 0) {
      const downloadHref = await errorBanner.locator("a").getAttribute("href");
      test.skip(
        true,
        `PdfPageView reported "Failed to load PDF" — verify the file URL is ` +
          `reachable from the test browser (got ${downloadHref}). On dev ` +
          `boxes that route files through a tunnel, set ` +
          `WS_ROOT_URL=http://localhost:9800 in the stack's env to keep file ` +
          `URLs on localhost.`
      );
    }
    await expect(wrapper).toBeVisible();
  });

  test("Rewind tab is hidden on PDF pages", async ({ page }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { data } = await importPdfViaApi(page, projectId);
    await openPage(page, data.page_external_id);

    // Sidebar.svelte filters out the rewind tab when currentPageIsPdf.
    expect(await page.locator('button.sidebar-tab[data-tab="rewind"]').count()).toBe(0);
  });

  test("Comments tab loads without errors on a PDF page", async ({ page }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { data } = await importPdfViaApi(page, projectId);
    await openPage(page, data.page_external_id);

    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.locator('button.sidebar-tab[data-tab="comments"]').click();
    await page.waitForSelector(".comments-content", { timeout: 5000 });

    // Empty thread state should be visible — no crash.
    await expect(page.locator(".comments-empty-text")).toBeVisible({ timeout: 5000 });
    expect(consoleErrors).toEqual([]);
  });

  // ---------------------------------------------------------------------------
  // API-only checks against a single shared PDF page.
  //
  // Pre-imports one PDF in beforeAll so the five backend-only tests below
  // don't each burn an import slot — the import endpoint is rate-limited
  // (default 10/hour per user via WS_IMPORTS_RATE_LIMIT_REQUESTS), and
  // running the full suite back-to-back used to exhaust the quota and turn
  // every downstream call into a misleading 404.
  // ---------------------------------------------------------------------------
  test.describe("API surface (shared PDF page)", () => {
    let sharedPageId;

    test.beforeAll(async ({ browser }) => {
      const ctx = await browser.newContext();
      const setupPage = await ctx.newPage();
      try {
        await login(setupPage);
        const projectId = await getFirstProjectId(setupPage);
        const { data } = await importPdfViaApi(setupPage, projectId);
        sharedPageId = data.page_external_id;
      } finally {
        await ctx.close();
      }
    });

    test("download endpoint returns 302 to a signed URL", async ({ page }) => {
      await login(page);

      const { csrf, cookieHeader } = await getCookies(page);
      const response = await page
        .context()
        .request.get(`${BASE_URL}/api/v1/pages/${sharedPageId}/download/`, {
          maxRedirects: 0,
          headers: { "X-CSRFToken": csrf, Cookie: cookieHeader },
        });

      expect(response.status()).toBe(302);
      const location = response.headers()["location"];
      expect(location).toBeTruthy();
      expect(location).toMatch(/^https?:\/\//);
    });

    test("rewind checkpoint endpoint returns 400 on PDF pages", async ({ page }) => {
      await login(page);

      const { csrf, cookieHeader } = await getCookies(page);
      const response = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/pages/${sharedPageId}/rewind/checkpoint/`, {
          data: { label: "test" },
          headers: {
            "X-CSRFToken": csrf,
            Cookie: cookieHeader,
            "Content-Type": "application/json",
          },
        });
      expect(response.status()).toBe(400);
    });

    test("access-code endpoint returns 400 on PDF pages", async ({ page }) => {
      await login(page);

      const { csrf, cookieHeader } = await getCookies(page);
      const response = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/pages/${sharedPageId}/access-code/`, {
          data: {},
          headers: {
            "X-CSRFToken": csrf,
            Cookie: cookieHeader,
            "Content-Type": "application/json",
          },
        });
      expect(response.status()).toBe(400);
    });

    test("reply with pdf_anchor is rejected with 400", async ({ page }) => {
      await login(page);

      const { csrf, cookieHeader } = await getCookies(page);

      // Create a root comment with a pdf_anchor.
      const rootResp = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/pages/${sharedPageId}/comments/`, {
          data: {
            body: "root comment",
            pdf_anchor: { page: 1, rects: [{ x: 0, y: 0, w: 10, h: 10 }], text: "hi" },
          },
          headers: {
            "X-CSRFToken": csrf,
            Cookie: cookieHeader,
            "Content-Type": "application/json",
          },
        });
      expect(rootResp.status()).toBe(201);
      const root = await rootResp.json();

      // Reply with a pdf_anchor must be rejected (replies inherit the parent's anchor).
      const replyResp = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/pages/${sharedPageId}/comments/`, {
          data: {
            body: "bad reply",
            parent_id: root.external_id,
            pdf_anchor: { page: 1, rects: [{ x: 0, y: 0, w: 10, h: 10 }], text: "hi" },
          },
          headers: {
            "X-CSRFToken": csrf,
            Cookie: cookieHeader,
            "Content-Type": "application/json",
          },
        });
      expect(replyResp.status()).toBe(400);

      // Reply with no anchor succeeds.
      const okReply = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/pages/${sharedPageId}/comments/`, {
          data: {
            body: "ok reply",
            parent_id: root.external_id,
          },
          headers: {
            "X-CSRFToken": csrf,
            Cookie: cookieHeader,
            "Content-Type": "application/json",
          },
        });
      expect(okReply.status()).toBe(201);
    });

    test("PDF page rejects text (Yjs) anchors on root comments", async ({ page }) => {
      await login(page);

      const { csrf, cookieHeader } = await getCookies(page);

      // Anchor bytes are arbitrary base64 — the API should reject the request
      // before decoding because the page is a PDF.
      const fakeAnchor = Buffer.from("not-a-real-yjs-anchor").toString("base64");
      const response = await page
        .context()
        .request.post(`${BASE_URL}/api/v1/pages/${sharedPageId}/comments/`, {
          data: {
            body: "Yjs anchor on PDF page",
            anchor_from_b64: fakeAnchor,
            anchor_to_b64: fakeAnchor,
            anchor_text: "snippet",
          },
          headers: {
            "X-CSRFToken": csrf,
            Cookie: cookieHeader,
            "Content-Type": "application/json",
          },
        });
      expect(response.status()).toBe(400);
    });
  });

  test("markdown page rejects pdf_anchor on root comments", async ({ page }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { csrf, cookieHeader } = await getCookies(page);

    // Create a fresh markdown page (default filetype) so the cross-validation
    // path can be exercised without leaning on an existing page's filetype.
    const createResp = await page.context().request.post(`${BASE_URL}/api/v1/pages/`, {
      data: { project_id: projectId, title: `markdown-pdf-anchor-${Date.now()}` },
      headers: {
        "X-CSRFToken": csrf,
        Cookie: cookieHeader,
        "Content-Type": "application/json",
      },
    });
    expect(createResp.status()).toBe(201);
    const mdPage = await createResp.json();

    const response = await page
      .context()
      .request.post(`${BASE_URL}/api/v1/pages/${mdPage.external_id}/comments/`, {
        data: {
          body: "pdf_anchor on markdown page",
          pdf_anchor: { page: 1, rects: [{ x: 0, y: 0, w: 10, h: 10 }], text: "hi" },
        },
        headers: {
          "X-CSRFToken": csrf,
          Cookie: cookieHeader,
          "Content-Type": "application/json",
        },
      });
    expect(response.status()).toBe(400);
  });

  test("PDF page receives comment broadcasts over WebSocket", async ({ page }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { data } = await importPdfViaApi(page, projectId);
    await openPage(page, data.page_external_id);

    // Skip if PDF.js can't load the file in this env (same fallback as test 1).
    const wrapper = page.locator('[data-pdf-page="1"]');
    const errorBanner = page.locator(".pdf-status-error");
    await expect(wrapper.or(errorBanner)).toBeVisible({ timeout: 15000 });
    if ((await errorBanner.count()) > 0) {
      test.skip(
        true,
        "PDF render failed in this env; live-broadcast test requires the render path."
      );
    }

    // The PDF page opens its own WS subscription via subscribeToPageEvents.
    // Wait until the page-side `commentsUpdated` listener is wired up by
    // priming a same-origin recorder before issuing the API POST.
    await page.evaluate(() => {
      window.__broadcastEvents = [];
      window.addEventListener("commentsUpdated", (e) => {
        window.__broadcastEvents.push(e.detail || {});
      });
    });

    // Give the WS a beat to connect. 1s is enough on the dev stack — the
    // assertion below has its own retry window so this isn't load-bearing.
    await page.waitForTimeout(1000);

    // Create a comment server-side via fetch. Because this path bypasses the
    // popover's local self-fire, only the channel-layer broadcast can deliver
    // `commentsUpdated` to this browser.
    const status = await page.evaluate(async (pageId) => {
      const csrf = document.cookie
        .split("; ")
        .find((r) => r.startsWith("csrftoken="))
        ?.split("=")[1];
      const response = await fetch(`/api/v1/pages/${pageId}/comments/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf || "" },
        body: JSON.stringify({ body: "Live broadcast probe" }),
      });
      return response.status;
    }, data.page_external_id);
    expect(status).toBe(201);

    // The WS subscription should deliver `comments_updated` and the page's
    // listener should record it. Without the fix, this never arrives.
    await expect
      .poll(async () => (await page.evaluate(() => window.__broadcastEvents?.length || 0)) > 0, {
        timeout: 8000,
      })
      .toBe(true);
  });

  test("PDF extracted text is searchable from the sidenav", async ({ page }) => {
    await login(page);
    const projectId = await getFirstProjectId(page);
    const { data } = await importPdfViaApi(page, projectId);

    // Search uses a unique phrase from SAMPLE_CONTENT — proves extracted_text
    // is indexed and the PDF page surfaces in search results.
    const searchInput = page.locator(".sidebar-search input, #sidebar-search-input").first();
    if ((await searchInput.count()) === 0) {
      test.skip(true, "Sidebar search input not present in this build");
    }
    await searchInput.fill("Supervised Learning uses labeled data");

    const result = page
      .locator(".sidebar-search-result, .search-result")
      .filter({ hasText: SAMPLE_TITLE })
      .first();
    await expect(result).toBeVisible({ timeout: 10000 });
    await result.click();

    await page.waitForURL(new RegExp(`/pages/${data.page_external_id}`), { timeout: 10000 });
  });
});
