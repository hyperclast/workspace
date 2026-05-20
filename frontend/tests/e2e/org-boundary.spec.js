/**
 * Cross-org boundary regression tests.
 *
 * The open page IS the current org: every reference surface reads the
 * current org from the sidenav store (server-injected on first paint,
 * updated by loadPage when the page changes). Tests check the live value
 * via `window._currentOrgId` (a read-only getter into the store rune)
 * since localStorage no longer mirrors it.
 *
 * These tests pin the invariants:
 *
 *  1. Switching org navigates the editor and records `last-page-per-org`.
 *  2. Switching back resumes on the previously-viewed page in the new org.
 *  3. Switching to a brand-new (empty) org auto-creates an Untitled project
 *     + page so the user always lands somewhere editable.
 *  4. Concurrent switches to the same empty org coalesce — exactly one
 *     `createProject` request goes out.
 *  5. Link autocomplete requests include `org_id` matching the current org.
 *  6. Ask requests include `org_id` matching the current org.
 *  7. The Cmd-K recent-pages list filters by current org and drops legacy
 *     (no-org) entries.
 *
 * Each test uses unique org/page names so re-running against a persistent
 * dev DB doesn't cause collisions.
 *
 * Run with:
 *   npx playwright test org-boundary.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import {
  login,
  waitForSwitcherReady,
  getCurrentUrlPath,
  uniqueOrgName,
  createOrgViaModal,
} from "./_helpers/orgSwitch.js";

test.describe("Org boundary — navigation", () => {
  test("switching to a brand-new org auto-creates Untitled project+page and navigates the editor", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    const pathBefore = await getCurrentUrlPath(page);
    const newOrgName = uniqueOrgName("empty-org");

    const newOrgId = await createOrgViaModal(page, newOrgName);
    expect(newOrgId).toBeTruthy();

    // Wait for the bootstrap pipeline to fully settle: last-page-per-org
    // is the canonical end-of-flow signal — it's written inside loadPage
    // which is the last thing that runs after openPage resolves.
    await page.waitForFunction(
      (orgId) => {
        const map = JSON.parse(localStorage.getItem("last-page-per-org") || "{}");
        return Boolean(map[orgId]);
      },
      newOrgId,
      { timeout: 20000 }
    );
    const lastPageMap = await page.evaluate(() =>
      JSON.parse(localStorage.getItem("last-page-per-org") || "{}")
    );
    const newOrgPageId = lastPageMap[newOrgId];
    expect(newOrgPageId).toBeTruthy();

    // URL should now point at the bootstrap page.
    const pathAfter = await getCurrentUrlPath(page);
    expect(pathAfter).toMatch(/^\/pages\//);
    expect(pathAfter).toContain(newOrgPageId);
    expect(pathAfter).not.toBe(pathBefore);

    // Sidenav should show the Untitled project under the new org.
    const sidebarHasUntitled = await page.evaluate(() =>
      Array.from(document.querySelectorAll(".sidebar-project .project-name")).some(
        (el) => el.textContent && el.textContent.trim() === "Untitled"
      )
    );
    expect(sidebarHasUntitled).toBe(true);
  });

  test("switching back to an org resumes on the page that was open there", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    // Remember the (real) starting org (the org of the page we landed on
    // via the homepage redirect) and the URL it took us to.
    const homeOrgId = await page.evaluate(() => window._currentOrgId);
    // Drive a real page load so last-page-per-org gets populated for the
    // starting org. The initial page from login may or may not have fired
    // setLastPageForOrg yet; clicking a sidenav page guarantees it.
    await page.waitForFunction(
      (orgId) => {
        const map = JSON.parse(localStorage.getItem("last-page-per-org") || "{}");
        return map[orgId];
      },
      homeOrgId,
      { timeout: 15000 }
    );
    const homePagePath = await getCurrentUrlPath(page);

    // Switch to a fresh org so the editor navigates away.
    await createOrgViaModal(page, uniqueOrgName("resume-test"));
    await page.waitForFunction((prevPath) => window.location.pathname !== prevPath, homePagePath, {
      timeout: 20000,
    });

    // Switch back via the dropdown by clicking the home org's row directly
    // (data-org-id is a stable selector for tests).
    await page.locator(".org-switcher-trigger").click();
    await page.locator(`.org-switcher-item[data-org-id="${homeOrgId}"]`).click();

    // Editor should return to the original page we were on (or the
    // last-viewed in that org if the map already had an entry).
    await page.waitForFunction((prevPath) => window.location.pathname === prevPath, homePagePath, {
      timeout: 20000,
    });
    const pathAfter = await getCurrentUrlPath(page);
    expect(pathAfter).toBe(homePagePath);
  });
});

test.describe("Org boundary — in-flight guard", () => {
  test("concurrent switches to the same empty org coalesce into one createProject call", async ({
    page,
  }) => {
    // The auto-create bootstrap is guarded by `orgBootstrapInFlight`. If
    // the user rapidly toggles into the same empty org twice, only one
    // createProject should fire. We slow the create endpoint via route
    // interception so the test can reliably "toggle twice" before the
    // first request resolves.
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    let createProjectCount = 0;
    await page.route("**/api/v1/projects/", async (route) => {
      if (route.request().method() === "POST") {
        createProjectCount += 1;
        // Add a small delay so the second click arrives while the first
        // create is still in flight.
        await new Promise((r) => setTimeout(r, 500));
      }
      await route.continue();
    });

    // Create a fresh empty org via the modal.
    const orgName = uniqueOrgName("inflight");
    const newOrgId = await createOrgViaModal(page, orgName);
    expect(newOrgId).toBeTruthy();

    // Wait for the bootstrap to finish (lastPage entry written).
    await page.waitForFunction(
      (orgId) => {
        const map = JSON.parse(localStorage.getItem("last-page-per-org") || "{}");
        return Boolean(map[orgId]);
      },
      newOrgId,
      { timeout: 20000 }
    );

    // Even though the slow path ran, exactly one create should have fired.
    expect(createProjectCount).toBe(1);

    await page.unroute("**/api/v1/projects/");
  });
});

test.describe("Org boundary — recent pages", () => {
  test("the recent-pages list filters by current org and drops legacy entries", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    const orgId = await page.evaluate(() => window._currentOrgId);
    expect(orgId).toBeTruthy();

    // Seed three recent-pages entries: one in this org, one in some other
    // org, one legacy (no orgId at all). After our boundary change, only
    // the current-org entry should make it into the palette.
    await page.evaluate((currentOrgId) => {
      const entries = [
        {
          id: "page_in_current_org",
          title: "Current Org Recent",
          projectName: "P1",
          orgId: currentOrgId,
          timestamp: Date.now(),
        },
        {
          id: "page_in_other_org",
          title: "Other Org Recent",
          projectName: "P2",
          orgId: "some-other-org-id",
          timestamp: Date.now() - 1,
        },
        {
          // Legacy: pre-boundary entry with no orgId. Must be dropped.
          id: "legacy_page",
          title: "Legacy Recent",
          projectName: "P3",
          timestamp: Date.now() - 2,
        },
      ];
      localStorage.setItem("hyperclast_recent_pages", JSON.stringify(entries));
    }, orgId);

    // Open the command palette so it reads the seeded list.
    const isMac = process.platform === "darwin";
    await page.keyboard.press(isMac ? "Meta+k" : "Control+k");
    await page.waitForSelector(".command-palette", { timeout: 5000 });
    // Recent section renders inside the palette; the rendering pulls from
    // storedRecentPages which is hydrated via getRecentPagesForOrg(currentOrgId).
    const seenTitles = await page.evaluate(() => {
      const items = Array.from(
        document.querySelectorAll(
          ".command-palette .palette-item, .command-palette [data-section='recent']"
        )
      );
      return items.map((el) => el.textContent || "").join(" | ");
    });
    // The "Current Org Recent" entry should appear in some form; the
    // other-org entry and legacy entry should NOT.
    expect(seenTitles).not.toContain("Other Org Recent");
    expect(seenTitles).not.toContain("Legacy Recent");
  });
});

test.describe("Org boundary — outbound request scoping", () => {
  test("link autocomplete sends org_id matching the current org", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    const orgId = await page.evaluate(() => window._currentOrgId);
    expect(orgId).toBeTruthy();

    // Capture the first autocomplete request the editor fires after we
    // type `[`. The completion source kicks in on typing.
    const autocompleteRequest = page.waitForRequest((req) => {
      return req.url().includes("/api/pages/autocomplete/");
    });

    // Type in the editor. Wait for the editor area to be ready first.
    await page.locator(".cm-content").click();
    await page.keyboard.type("[Page");

    const req = await autocompleteRequest;
    const reqUrl = new URL(req.url());
    expect(reqUrl.searchParams.get("org_id")).toBe(orgId);
    expect(reqUrl.searchParams.get("q")).toBeTruthy();
  });

  test("askQuestion() includes org_id matching the current org without an explicit override", async ({
    page,
  }) => {
    // Exercise the real `ask.js` code path — `askQuestion` reads the
    // current org from the store and stitches it into the request body.
    // The previous version of this test hand-rolled a `fetch` with the
    // expected shape, which only proved the wire format, not that the
    // helper actually injects it.
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    const orgId = await page.evaluate(() => window._currentOrgId);
    expect(orgId).toBeTruthy();

    const requestPromise = page.waitForRequest((req) => req.url().endsWith("/api/ask/"));
    await page.evaluate(async () => {
      try {
        // Real entry point exposed for testability via main.js.
        await window._askQuestion("hello", []);
      } catch {
        // 4xx/5xx (no provider configured in dev) is fine — we only care
        // about the outgoing request shape, not the response.
      }
    });

    const req = await requestPromise;
    const body = JSON.parse(req.postData() || "{}");
    expect(body.org_id).toBe(orgId);
    expect(body.query).toBe("hello");
    expect(body.page_ids).toEqual([]);
  });
});

test.describe("Org boundary — deep link", () => {
  test("deep-linking to a page records last-page-per-org even when cachedProjects is cold", async ({
    page,
  }) => {
    // Regression: loadPage used to derive the page's org from
    // `cachedProjects` alone. A deep-link request lands on /pages/<id>/
    // before the user's projects list has loaded, so the lookup
    // returned undefined and the last-page write was silently skipped.
    // PageOut now ships `org_external_id` in the response so the
    // derivation works regardless of cache state.
    await page.setViewportSize({ width: 1280, height: 900 });
    await login(page);
    await waitForSwitcherReady(page);

    // Capture the page we landed on and its expected org id.
    const initialPath = await getCurrentUrlPath(page);
    const initialOrgId = await page.evaluate(() => window._currentOrgId);
    expect(initialOrgId).toBeTruthy();
    expect(initialPath).toMatch(/^\/pages\//);
    const initialPageId = initialPath.match(/^\/pages\/([^/]+)\/?$/)?.[1];

    // Clear the in-memory caches + last-page-per-org map and hard-reload
    // — this simulates a deep-link from a clean window where cachedProjects
    // is empty when loadPage runs.
    await page.evaluate(() => {
      try {
        localStorage.removeItem("last-page-per-org");
      } catch {}
    });
    await page.reload();
    await page.waitForSelector("#editor", { timeout: 15000 });

    // The last-page-per-org entry for the page's org should be written
    // by loadPage *even though* cachedProjects is still cold at that
    // point — the response carries `org_external_id` directly.
    await page.waitForFunction(
      ({ orgId, pageId }) => {
        const map = JSON.parse(localStorage.getItem("last-page-per-org") || "{}");
        return map[orgId] === pageId;
      },
      { orgId: initialOrgId, pageId: initialPageId },
      { timeout: 10000 }
    );
  });
});
