/**
 * Org switch during an in-flight Ask request.
 *
 * Page-canonical invariant test (gap §8.17). The user kicks off an Ask
 * while on Org A, switches to Org B before the response returns. The
 * pinned invariant is that the in-flight request was *scoped at issue
 * time* — `body.org_id === <Org A>` — so even if the response lands while
 * the UI now reflects Org B, the backend can't have returned citations
 * from Org B's pages (the three-tier filter chains `org_id` into
 * `project__org__external_id`).
 *
 * Why pin the issue-time scoping and not "response is dropped": there is
 * no `askSwitchSeq` analog of `orgSwitchSeq` in `ask.js` today. The
 * security boundary is enforced at the wire, not in the UI sequence
 * guard. Asserting on the wire is the right level of pin — a future
 * sequence guard can be added without invalidating this test, and this
 * test's failure mode (request body's org_id matches Org B after a
 * switch) would be a genuine security regression.
 *
 * Run with:
 *   npx playwright test ask-org-switch.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import {
  login,
  waitForSwitcherReady,
  getCurrentUrlPath,
  uniqueOrgName,
  createOrgViaModal,
} from "./_helpers/orgSwitch.js";

test.describe("Ask + org switch", () => {
  test("an Ask issued in Org A is scoped to Org A even when the user switches to Org B mid-flight", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    const orgAId = await page.evaluate(() => window._currentOrgId);
    expect(orgAId).toBeTruthy();

    // Create Org B so we have a target to switch into. The bootstrap path
    // navigates us to Org B's Untitled page; we then switch back to Org A
    // so the Ask kickoff happens in Org A's context.
    const orgBId = await createOrgViaModal(page, uniqueOrgName("ask-switch"));
    expect(orgBId).not.toBe(orgAId);

    // `setLastPageForOrg` (which writes `last-page-per-org[orgId]`) runs
    // inside `loadPage`, but `pushState` runs *after* loadPage resolves.
    // Reading the URL right after the localStorage check sees the
    // pre-switch URL — only safe to read once both signals agree.
    await page.waitForFunction(
      (orgId) => {
        const map = JSON.parse(localStorage.getItem("last-page-per-org") || "{}");
        const lastPageId = map[orgId];
        if (!lastPageId) return false;
        const match = window.location.pathname.match(/^\/pages\/([^/]+)\/?$/);
        return Boolean(match && match[1] === lastPageId);
      },
      orgBId,
      { timeout: 20000 }
    );
    const orgBPagePath = await getCurrentUrlPath(page);

    // Switch back to Org A via the dropdown. Wait for both the URL change
    // and the rune flip so the Ask kickoff lands in fully-settled Org A
    // state (not a half-transitioned A→B→A intermediate).
    await page.locator(".org-switcher-trigger").click();
    await page.locator(`.org-switcher-item[data-org-id="${orgAId}"]`).click();
    await page.waitForFunction((prev) => window.location.pathname !== prev, orgBPagePath, {
      timeout: 20000,
    });
    await page.waitForFunction((orgId) => window._currentOrgId === orgId, orgAId, {
      timeout: 10000,
    });

    // Intercept /api/ask/ and hold the response so we can guarantee the
    // request is still in flight when we switch. We fulfill it AFTER the
    // org switch so the timeline is unambiguous:
    //   t0: Ask kicked off (request fires, body.org_id = Org A)
    //   t1: route handler captures the request and pauses
    //   t2: user clicks Org B → setCurrentOrgId(Org B) → URL changes
    //   t3: route handler fulfills with a stub response
    //   t4: assertions run on the captured request body
    let capturedRequestBody = null;
    let releaseResponse;
    const responseHeld = new Promise((resolve) => {
      releaseResponse = resolve;
    });
    await page.route("**/api/ask/", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      capturedRequestBody = JSON.parse(route.request().postData() || "{}");
      await responseHeld;
      // Stub answer with no citations — the test asserts on the wire-level
      // request body, not on any rendered output, so the response body
      // shape just needs to be parseable by ask.js.
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ answer: "(stubbed)", citations: [] }),
      });
    });

    // Kick off the Ask without awaiting the page-side promise — the fetch
    // is initiated synchronously inside `_askQuestion`, so by the time
    // page.evaluate returns the request is already in flight (and pinned
    // by our route handler). Errors inside the promise are fine — no
    // provider configured in dev — we only care about the outgoing body.
    await page.evaluate(() => {
      window._askQuestion("scoped to org A?", []).catch(() => {});
    });

    // The route handler runs in the test process, not the page context,
    // so page.waitForFunction can't observe `capturedRequestBody`. Poll
    // the outer variable directly with a small backoff cap.
    for (let i = 0; i < 50 && capturedRequestBody === null; i++) {
      await page.waitForTimeout(50);
    }
    expect(capturedRequestBody).not.toBeNull();
    // Issue-time scoping: the in-flight request carried Org A's id, NOT
    // Org B's (which is what the user is about to switch into).
    expect(capturedRequestBody.org_id).toBe(orgAId);

    // Now switch to Org B mid-flight. The dropdown click is the same path
    // a real user takes — exercises setCurrentOrgId → onOrgChanged →
    // fetchProjects → renderSidenav → navigate. The held Ask response is
    // still pending in the route handler.
    await page.locator(".org-switcher-trigger").click();
    await page.locator(`.org-switcher-item[data-org-id="${orgBId}"]`).click();
    await page.waitForFunction((orgId) => window._currentOrgId === orgId, orgBId, {
      timeout: 20000,
    });

    // Sanity: the captured request body has NOT been re-issued or mutated
    // with Org B's id — it was frozen at send time. (Playwright's request
    // body is immutable post-capture, but asserting protects against a
    // future refactor where ask.js retries / re-sends after a switch.)
    expect(capturedRequestBody.org_id).toBe(orgAId);
    expect(capturedRequestBody.org_id).not.toBe(orgBId);

    // Release the response. Ask.js will resolve its promise — the test
    // doesn't assert UI rendering because there's no current guard
    // against late-render leaks; the security boundary is the wire-level
    // org_id, which is what we pinned above.
    releaseResponse();

    // Drain pending microtasks so the stubbed response is consumed before
    // route teardown, otherwise Playwright complains about an unhandled
    // route during context close.
    await page.waitForTimeout(100);
    await page.unroute("**/api/ask/");
  });
});
