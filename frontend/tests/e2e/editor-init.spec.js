/**
 * Regression guard for the post-login editor-mount invariant.
 *
 * After logging in, the app must:
 *   1. Render `#editor` in the DOM.
 *   2. Mount CodeMirror inside it (`.cm-content` becomes visible).
 *   3. Expose the EditorView globally as `window.editorView`.
 *   4. Hydrate `state.doc` with the page's REST content.
 *
 * All of the above must happen within a single second of `#editor`
 * appearing, with no `pageerror` events firing during init. Roughly half
 * of the E2E suite implicitly depends on this invariant — when it breaks,
 * symptoms scatter across many specs and the root cause is hard to find.
 * This spec exists to surface the regression directly.
 *
 * Run with:
 *   npm run test:e2e -- editor-init.spec.js
 */

import { test, expect } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";

test.describe("Editor initialization after login", () => {
  test("CodeMirror mounts and editorView is exposed within 1s of #editor appearing", async ({
    page,
  }) => {
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));

    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector("#login-email", { timeout: 10000 });
    await page.fill("#login-email", TEST_EMAIL);
    await page.fill("#login-password", TEST_PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForSelector("#editor", { timeout: 20000 });
    const editorAppearedAt = Date.now();

    await page.waitForSelector(".cm-content", { timeout: 5000 });
    const cmContentDelayMs = Date.now() - editorAppearedAt;

    await page.waitForFunction(
      () => !!window.editorView && (window.editorView.state?.doc?.length ?? 0) > 0,
      { timeout: 5000 }
    );

    const cmContentBox = await page.locator(".cm-content").boundingBox();
    expect(cmContentBox, ".cm-content must have a non-zero bounding box").not.toBeNull();
    expect(cmContentBox.width).toBeGreaterThan(0);
    expect(cmContentBox.height).toBeGreaterThan(0);

    expect(
      cmContentDelayMs,
      `.cm-content must appear within 1000ms of #editor (took ${cmContentDelayMs}ms)`
    ).toBeLessThan(1000);

    expect(pageErrors, `no page errors during init, got: ${pageErrors.join(" | ")}`).toEqual([]);
  });
});
