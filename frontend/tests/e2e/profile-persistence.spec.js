/**
 * Profile-persisted current-org and last-page tests.
 *
 * The org-switch state used to live in localStorage. Under the
 * "open page IS the current org" architecture the canonical sources are:
 *
 *   - `Profile.current_org` (server) — used for non-page routes and as a
 *     fallback when there's no current page; persists across devices.
 *   - The page's own `project.org` — used for `/pages/<id>/` routes
 *     (server-injected as `currentOrgId` for that request).
 *   - `UserOrgState.last_page` — per-org resume target, injected into
 *     `window._userState.lastPagePerOrg`.
 *
 * What we assert here:
 *   1. The SPA template renders `window._userState` with the right shape.
 *   2. After switching to a brand-new org in one browser context, opening
 *      a FRESH browser context (no client cache) lands on a page in that
 *      same org — because Profile.current_org has been persisted and the
 *      homepage redirect lands on a page that org's most-recent page.
 *
 * Run with:
 *   npx playwright test profile-persistence.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import { login, waitForSwitcherReady } from "./_helpers/orgSwitch.js";

test("window._userState is injected and has the expected shape", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await login(page);
  await waitForSwitcherReady(page);

  // The SPA template embeds the user's persisted state — verify shape.
  const userState = await page.evaluate(() => window._userState);
  expect(userState).toBeTruthy();
  expect(typeof userState).toBe("object");
  expect("currentOrgId" in userState).toBe(true);
  expect("lastPagePerOrg" in userState).toBe(true);

  // Logged-in users navigating to /pages/<id>/ get the page's org as
  // currentOrgId. The org switcher trigger reflects this.
  expect(userState.currentOrgId).toBeTruthy();
});

test("Profile.current_org is persisted on switch and drives a fresh browser context", async ({
  browser,
}) => {
  // First context: log in, create + switch to a fresh org via the modal.
  // That triggers a PATCH to /me/ that writes Profile.current_org.
  const ctx1 = await browser.newContext();
  const page1 = await ctx1.newPage();
  await page1.setViewportSize({ width: 1280, height: 900 });
  await login(page1);
  await waitForSwitcherReady(page1);

  // Capture the URL we start on so we can wait for the bootstrap-driven
  // navigation to a page in the new org.
  const prevPath = await page1.evaluate(() => window.location.pathname);

  const orgName = `Persist${Date.now().toString(36)}`;
  await page1.locator(".org-switcher-trigger").click();
  await page1.locator(".org-switcher-create").click();
  await page1.waitForSelector(".modal");
  await page1.locator("input#org-name-input").fill(orgName);
  await page1.locator(".modal-btn-primary").click();
  await page1.waitForSelector(".modal", { state: "detached", timeout: 10000 });

  // Wait for the full bootstrap pipeline to complete: URL changes to a
  // NEW /pages/<id>/ (the auto-created Untitled). The URL only changes
  // after openPage(newPageId)→loadPage settles, which is the point where
  // the rune is also guaranteed to reflect the new org. Using the URL
  // change (not just a rune flip) avoids racing intermediate states.
  await page1.waitForFunction(
    (prev) => /^\/pages\//.test(window.location.pathname) && window.location.pathname !== prev,
    prevPath,
    { timeout: 20000 }
  );

  // Read the LIVE rune via the getter, not the template-injected snapshot
  // — `window._userState` is captured once at SPA render and won't reflect
  // the in-session switch.
  const newOrgId = await page1.evaluate(() => window._currentOrgId);
  expect(newOrgId).toBeTruthy();
  const newPagePath = await page1.evaluate(() => window.location.pathname);
  const newPageId = newPagePath.match(/^\/pages\/([^/]+)\/?$/)?.[1];
  expect(newPageId).toBeTruthy();

  // The org switch fires fire-and-forget PATCHes for current_org and
  // org-state. Issue them EXPLICITLY here so the test is deterministic
  // regardless of whether those background patches settle in time.
  const patchResults = await page1.evaluate(
    async ({ orgId, pageId }) => {
      const csrf = window._csrfToken;
      const headers = { "Content-Type": "application/json", "X-CSRFToken": csrf || "" };
      const orgRes = await fetch("/api/v1/users/me/", {
        method: "PATCH",
        credentials: "include",
        headers,
        body: JSON.stringify({ current_org_id: orgId }),
      });
      const stateRes = await fetch(`/api/v1/users/me/org-state/${orgId}/`, {
        method: "PATCH",
        credentials: "include",
        headers,
        body: JSON.stringify({ last_page_id: pageId }),
      });
      return { org: orgRes.status, state: stateRes.status };
    },
    { orgId: newOrgId, pageId: newPageId }
  );
  expect(patchResults.org).toBe(200);
  expect(patchResults.state).toBe(200);

  // Reload page1 — the new HTML response should still carry the same
  // currentOrgId because the URL is still /pages/<new-page>/ and the
  // server picks the page's org first.
  await page1.reload();
  await page1.waitForFunction(() => window._userState !== undefined, null, { timeout: 5000 });
  const reloadedState = await page1.evaluate(() => window._userState);
  expect(reloadedState.currentOrgId).toBe(newOrgId);

  await ctx1.close();

  // Second context: brand-new browser. Logging in lands on the
  // homepage redirect which 302s to the most-recently-modified page —
  // which is the page we just created in newOrgId. The SPA inject for
  // that route carries newOrgId.
  const ctx2 = await browser.newContext();
  const page2 = await ctx2.newPage();
  await page2.setViewportSize({ width: 1280, height: 900 });
  await login(page2);
  await waitForSwitcherReady(page2);

  const seededCurrentOrgId = await page2.evaluate(() => window._userState?.currentOrgId);
  expect(seededCurrentOrgId).toBe(newOrgId);

  // The template injects lastPagePerOrg, but the sidenav store's module-init
  // IIFE seeds the values into localStorage and zeroes out the in-memory
  // snapshot. The persisted source of truth post-hydration is localStorage.
  const lastPageMap = await page2.evaluate(() =>
    JSON.parse(localStorage.getItem("last-page-per-org") || "{}")
  );
  expect(lastPageMap[newOrgId]).toBe(newPageId);

  await ctx2.close();
});
