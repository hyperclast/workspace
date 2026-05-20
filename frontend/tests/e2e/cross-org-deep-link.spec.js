/**
 * Cross-org deep link — the OrgSwitcher follows the open page.
 *
 * Page-canonical invariant test (gap §8.15): when the user deep-links to a
 * `/pages/<id>/` URL for a page whose project lives in an org *other* than
 * the user's currently-selected one, the OrgSwitcher trigger label and the
 * sidenav must both upgrade to the page's org. The autocomplete/Ask paths
 * are already exercised by `org-boundary.spec.js`; what this spec pins is
 * the visual end of the fan-out — specifically the trigger label, whose
 * lag was the M-2 bug fixed by adding `hyperclast:current-org-changed`.
 *
 * Run with:
 *   npx playwright test cross-org-deep-link.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import {
  login,
  waitForSwitcherReady,
  getCurrentUrlPath,
  uniqueOrgName,
  createOrgViaModal,
} from "./_helpers/orgSwitch.js";

test.describe("Cross-org deep link", () => {
  test("opening a page in Org B from Org A updates the switcher label and sidenav", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    // Capture the home-org context (Org A). The dev user's homepage redirect
    // lands on a page in whichever org is currently persisted as their
    // `current_org`; we don't care which one — we only need its id + label so
    // we can switch *back* into it before deep-linking out to Org B.
    const homeOrgId = await page.evaluate(() => window._currentOrgId);
    expect(homeOrgId).toBeTruthy();
    const homeOrgLabel = (await page.locator(".org-switcher-trigger").textContent()).trim();
    expect(homeOrgLabel.length).toBeGreaterThan(0);

    // Create Org B with a unique name so the assertion on the label is
    // unambiguous (no collision with whatever Org A is called in the dev DB).
    const orgBName = uniqueOrgName("deep-link");
    const orgBId = await createOrgViaModal(page, orgBName);
    expect(orgBId).toBeTruthy();
    expect(orgBId).not.toBe(homeOrgId);

    // The create-flow bootstraps an Untitled page; wait for the URL to settle
    // on it so we can capture its id for the deep-link step. We have to wait
    // for BOTH the last-page-per-org entry AND the URL pushState to land —
    // `setLastPageForOrg` fires inside `loadPage`, but `pushState` runs
    // *after* loadPage resolves (see `openPage()` in main.js). Reading
    // `window.location.pathname` right after the localStorage check captures
    // the pre-switch URL, which against a dev DB seeded by prior runs may
    // point at a leftover org's page. That stale path then deep-links into
    // the wrong org and the rest of the test asserts against the wrong rune.
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
    expect(orgBPagePath).toMatch(/^\/pages\//);
    const orgBPageId = orgBPagePath.match(/^\/pages\/([^/]+)\/?$/)?.[1];
    expect(orgBPageId).toBeTruthy();

    // Switch back to Org A by clicking its row in the dropdown. Wait for the
    // URL to leave Org B's page so we know the switch has fully taken effect
    // (label, sidenav, and current org are all in Org A state).
    await page.locator(".org-switcher-trigger").click();
    await page
      .locator(`.org-switcher-popover .org-switcher-item[data-org-id="${homeOrgId}"]`)
      .click();
    await page.waitForFunction((prev) => window.location.pathname !== prev, orgBPagePath, {
      timeout: 20000,
    });
    await page.waitForFunction((orgId) => window._currentOrgId === orgId, homeOrgId, {
      timeout: 10000,
    });

    // Deep-link directly to Org B's page. This is the cross-org scenario:
    // the user is in Org A, navigates to a `/pages/<id>/` URL whose page
    // lives in Org B. `loadPage()` derives the page's org from the response
    // (`PageOut.org_external_id`) and calls `setCurrentOrgId`, which now
    // fans out to the OrgSwitcher via `hyperclast:current-org-changed`.
    await page.goto(orgBPagePath);
    await page.waitForSelector("#editor", { timeout: 15000 });

    // The current-org rune flips first; wait for it so subsequent label /
    // sidenav reads happen against post-switch state.
    await page.waitForFunction((orgId) => window._currentOrgId === orgId, orgBId, {
      timeout: 15000,
    });

    // OrgSwitcher trigger label must now read Org B. This is the M-2 pin:
    // prior to the event-channel fix the label kept showing the previous
    // org's name even though autocomplete/Ask had already moved.
    await expect(page.locator(".org-switcher-trigger")).toHaveText(new RegExp(orgBName, "i"), {
      timeout: 10000,
    });

    // The dropdown must reflect Org B as active (single `.active` row,
    // matching Org B's id) — proves the popover's internal selection state
    // also tracked the deep-link-driven change.
    await page.locator(".org-switcher-trigger").click();
    await expect(page.locator(".org-switcher-item.active")).toHaveCount(1);
    await expect(page.locator(`.org-switcher-item.active[data-org-id="${orgBId}"]`)).toBeVisible();
    await page.keyboard.press("Escape");

    // The sidenav must have re-rendered with Org B's project list. Org B was
    // just created so its only project is the auto-bootstrapped "Untitled" —
    // assert that's what we see, not whatever Org A's projects were.
    await page.waitForFunction(
      () => {
        const names = Array.from(document.querySelectorAll(".sidebar-project .project-name")).map(
          (el) => (el.textContent || "").trim()
        );
        return names.length > 0 && names.every((n) => n === "Untitled");
      },
      null,
      { timeout: 15000 }
    );
  });
});
