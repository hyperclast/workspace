/**
 * Scenario F — Rapid org switching across three distinct pre-populated orgs.
 *
 * `org-boundary.spec.js` already covers the empty-org coalesce case (two
 * concurrent switches to the SAME empty org collapse into one createProject).
 * This spec pins the *three-distinct-orgs* form of Scenario F: switching
 * Start → A → B → C in rapid succession must (a) fan out three
 * `/api/v1/projects/?org_id=...` requests, (b) drop the intermediate ones
 * via `orgSwitchSeq`, and (c) land on the LAST clicked org's entry page —
 * label, sidenav, URL, and `window._currentOrgId` all agreeing on Org C.
 *
 * Mechanics:
 *   - Provision a synthetic user with four orgs (Start, A, B, C) via
 *     `docker exec`; each non-start org has one project with one distinctly
 *     titled page, so the URL/sidenav assertion is unambiguous.
 *   - Slow `GET /api/v1/projects/?org_id=...` via `page.route` to a 300ms
 *     delay so all three `setCurrentOrgId` calls finish (seq becomes 3)
 *     before any `fetchProjects` resolves. Without this slowdown the dev
 *     DB is fast enough that the A response could land before the B click
 *     and we'd race the very behavior under test.
 *   - Fire the three switcher selects from one `page.evaluate` so they
 *     happen in a single synchronous task — tighter than UI clicking,
 *     matching the "Promise.all dispatch" sketch in the manual.
 *
 * Run with:
 *   TEST_DOCKER_CONTAINER=backend-hyper-9800-ws-web-1 \
 *     npx playwright test rapid-org-switch.spec.js --reporter=list
 */

import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import { BASE_URL } from "./_helpers/orgSwitch.js";

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

function runShell(py) {
  return execSync(`docker exec -i ${DOCKER_CONTAINER} python manage.py shell`, {
    encoding: "utf-8",
    timeout: 30000,
    input: py,
  });
}

function provisionFourOrgFixture() {
  const ts = Date.now().toString(36);
  const email = `ros-${ts}@e2e.local`;
  const password = "ros-e2e-pw";

  const py = `
from allauth.account.models import EmailAddress
from users.models import User, Org, OrgMember
from users.constants import OrgMemberRole
from pages.models import Project, Page

user, _ = User.objects.get_or_create(
    username="${email}", defaults={"email": "${email}"}
)
user.set_password("${password}")
user.email = "${email}"
user.save()
EmailAddress.objects.update_or_create(
    user=user, email="${email}",
    defaults={"verified": True, "primary": True},
)

# Four orgs: Start (where we land after login) + A, B, C (the rapid-click
# targets). Names include ts so re-runs don't collide.
org_start = Org.objects.create(name="ROStart-${ts}")
org_a = Org.objects.create(name="ROOrgA-${ts}")
org_b = Org.objects.create(name="ROOrgB-${ts}")
org_c = Org.objects.create(name="ROOrgC-${ts}")
for org in (org_start, org_a, org_b, org_c):
    OrgMember.objects.create(org=org, user=user, role=OrgMemberRole.ADMIN.value)

# Each org gets one project + one distinctly-titled page. The Start page
# is needed so the post-login homepage redirect has somewhere to land
# (otherwise loginAs()'s #editor wait hangs — same lesson as
# per-org-daily-note.spec.js).
proj_start = Project.objects.create(org=org_start, name="ROProj-Start-${ts}", creator=user, org_members_can_access=True)
proj_a = Project.objects.create(org=org_a, name="ROProj-A-${ts}", creator=user, org_members_can_access=True)
proj_b = Project.objects.create(org=org_b, name="ROProj-B-${ts}", creator=user, org_members_can_access=True)
proj_c = Project.objects.create(org=org_c, name="ROProj-C-${ts}", creator=user, org_members_can_access=True)

page_start = Page.objects.create(
    project=proj_start, creator=user, title="ROStart-Landing-${ts}",
    details={"content": "start", "filetype": "md", "schema_version": 1},
)
page_a = Page.objects.create(
    project=proj_a, creator=user, title="ROPage-A-${ts}",
    details={"content": "a", "filetype": "md", "schema_version": 1},
)
page_b = Page.objects.create(
    project=proj_b, creator=user, title="ROPage-B-${ts}",
    details={"content": "b", "filetype": "md", "schema_version": 1},
)
page_c = Page.objects.create(
    project=proj_c, creator=user, title="ROPage-C-${ts}",
    details={"content": "c", "filetype": "md", "schema_version": 1},
)

# Pre-pick Start so the login redirect lands there, NOT on one of the
# rapid-click target orgs. If we landed on Org A, the first click on
# "Org A" would be a setCurrentOrgId no-op (early-return when
# orgId === currentOrgId) and only two real switches would fire — the
# seq guard test needs three.
user.profile.current_org = org_start
user.profile.org_state = {}
user.profile.save(update_fields=["current_org", "org_state", "modified"])

print(f"USER_ID={user.id}")
print(f"EMAIL={user.email}")
print(f"PASSWORD=${password}")
print(f"ORG_START_ID={org_start.external_id}")
print(f"ORG_A_ID={org_a.external_id}")
print(f"ORG_B_ID={org_b.external_id}")
print(f"ORG_C_ID={org_c.external_id}")
print(f"ORG_C_NAME={org_c.name}")
print(f"PAGE_START_ID={page_start.external_id}")
print(f"PAGE_A_ID={page_a.external_id}")
print(f"PAGE_B_ID={page_b.external_id}")
print(f"PAGE_C_ID={page_c.external_id}")
print(f"PAGE_C_TITLE={page_c.title}")
print(f"PAGE_A_TITLE={page_a.title}")
print(f"PAGE_B_TITLE={page_b.title}")
`;
  const stdout = runShell(py);
  const grab = (key) => {
    const m = stdout.match(new RegExp(`^${key}=(.+)$`, "m"));
    if (!m) throw new Error(`provision script did not emit ${key}; stdout: ${stdout}`);
    return m[1].trim();
  };
  return {
    userId: grab("USER_ID"),
    email: grab("EMAIL"),
    password: grab("PASSWORD"),
    orgStartId: grab("ORG_START_ID"),
    orgAId: grab("ORG_A_ID"),
    orgBId: grab("ORG_B_ID"),
    orgCId: grab("ORG_C_ID"),
    orgCName: grab("ORG_C_NAME"),
    pageStartId: grab("PAGE_START_ID"),
    pageAId: grab("PAGE_A_ID"),
    pageBId: grab("PAGE_B_ID"),
    pageCId: grab("PAGE_C_ID"),
    pageCTitle: grab("PAGE_C_TITLE"),
    pageATitle: grab("PAGE_A_TITLE"),
    pageBTitle: grab("PAGE_B_TITLE"),
  };
}

function cleanupFixture(userId) {
  const py = `
from users.models import User
u = User.objects.filter(id=${userId}).first()
if u is not None:
    u.profile.org_state = {}
    u.profile.save(update_fields=["org_state", "modified"])
print("CLEANED")
`;
  runShell(py);
}

async function loginAs(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
}

test.describe("Rapid org switching across three distinct orgs (Scenario F)", () => {
  test("Start → A → B → C in one task lands on Org C; A and B fetches are dropped", async ({
    browser,
  }) => {
    test.skip(
      !isDockerContainerAvailable(),
      `Docker container ${DOCKER_CONTAINER} not found — required to seed rapid-org-switch scenario`
    );

    const fx = provisionFourOrgFixture();
    try {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await page.setViewportSize({ width: 1280, height: 900 });

      // Capture console errors — Scenario F's expected behavior includes
      // "no JavaScript errors". The browser also logs generic
      // "Failed to load resource: ... 401/404" entries for any non-2xx
      // network response; those are *expected* during this race because
      // the seq guard explicitly drops the intermediate switches'
      // fetchPage/openPage chains, which can momentarily target a stale
      // org's page before being superseded. We filter those out and
      // only fail on real script-level errors.
      const consoleErrors = [];
      const consoleNav = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") {
          const txt = msg.text();
          if (!/Failed to load resource:/.test(txt)) {
            consoleErrors.push(txt);
          }
        }
        const txt = msg.text();
        if (/\[Nav\]|\[Org\]|openPage|loadPage/.test(txt)) {
          consoleNav.push(`${msg.type()}:${txt}`);
        }
      });

      await loginAs(page, fx.email, fx.password);

      // Confirm the landing org is Start (not one of the click targets) so
      // each of the three upcoming setCurrentOrgId calls is a genuine
      // switch (no early-return on orgId === currentOrgId).
      await page.waitForFunction((startId) => window._currentOrgId === startId, fx.orgStartId, {
        timeout: 10000,
      });

      // Wait for the post-login bootstrap to fully settle before arming the
      // slow route. The SPA's boot calls fetchProjects → openPage(pageStart)
      // → loadPage; if the route delay is in place during this flow it can
      // still be racing when we issue the rapid clicks, and the boot's
      // tail-end calls become indistinguishable from our switches. We
      // gate on lastPagePerOrg[Start] being populated — that key is the
      // last write in loadPage's flow (setLastPageForOrg fires after the
      // page is mounted).
      await page.waitForFunction(
        (startId) => {
          const map = JSON.parse(localStorage.getItem("last-page-per-org") || "{}");
          return Boolean(map[startId]);
        },
        fx.orgStartId,
        { timeout: 15000 }
      );

      // Slow GET /api/v1/projects/?... so all three setCurrentOrgId calls
      // bump orgSwitchSeq before any fetchProjects resolves. Without this
      // the dev DB returns fast enough that A's response can apply before
      // B's switch fires, defeating the very race we're pinning.
      await page.route(/\/api\/(?:v1\/)?projects\/\?[^/]*$/, async (route) => {
        const req = route.request();
        if (req.method() === "GET") {
          await new Promise((r) => setTimeout(r, 300));
        }
        await route.continue();
      });

      // Collect every projects-list request fired during the rapid sequence
      // so we can assert (a) all three switches sent one each, and (b) the
      // applied one is Org C's.
      const projectsRequests = [];
      page.on("request", (req) => {
        if (/\/api\/(?:v1\/)?projects\/\?[^/]*\borg_id=/.test(req.url())) {
          projectsRequests.push(req.url());
        }
      });

      // Verify the OrgSwitcher root is in the DOM — the delegated click
      // handler (OrgSwitcher.svelte:100) is bound here and only reacts
      // to bubbling clicks from descendant elements with `data-org-action`.
      await page.waitForSelector(".org-switcher", { timeout: 5000 });

      // Fire all three switches in one synchronous task by INJECTING
      // synthetic select buttons into `.org-switcher`. This bypasses the
      // popover open/close cycle entirely — the delegated handler still
      // fires because the synthetic buttons are descendants of the
      // listener root, and they're freshly attached at click time so
      // there's no detached-element risk from Svelte re-rendering the
      // popover. Each synthetic button has the same dataset shape
      // (`data-org-action="select"`, `data-org-id=...`) that the
      // popover rows render with, so the handler treats them identically.
      //
      // All three .click() calls happen synchronously within this task;
      // Svelte's $state updates from handleRootClick batch into the next
      // microtask. The end state after the third click is therefore:
      // orgSwitchSeq=3, currentOrgId=C, three pending fetchProjects
      // awaits. Only C's resolve will pass `seq === orgSwitchSeq`.
      await page.evaluate(
        ({ a, b, c }) => {
          const root = document.querySelector(".org-switcher");
          if (!root) throw new Error(".org-switcher root not in DOM");
          const fireSelect = (orgId) => {
            const btn = document.createElement("button");
            btn.setAttribute("data-org-action", "select");
            btn.setAttribute("data-org-id", orgId);
            btn.style.display = "none";
            root.appendChild(btn);
            btn.click();
            btn.remove();
          };
          fireSelect(a);
          fireSelect(b);
          fireSelect(c);
        },
        { a: fx.orgAId, b: fx.orgBId, c: fx.orgCId }
      );

      // Wait for the current-org rune to settle on C and the URL to
      // navigate to Org C's only page. The seq guard means only C's
      // fetchProjects → renderSidenav → navigateToOrgEntryPage chain runs
      // to completion; A's and B's bail at `if (seq !== orgSwitchSeq) return`.
      await page.waitForFunction((cId) => window._currentOrgId === cId, fx.orgCId, {
        timeout: 15000,
      });
      try {
        await page.waitForFunction(
          (pageCId) => {
            const m = window.location.pathname.match(/^\/pages\/([^/]+)\/?$/);
            return Boolean(m && m[1] === pageCId);
          },
          fx.pageCId,
          { timeout: 15000 }
        );
      } catch (e) {
        const diag = await page.evaluate(() => ({
          path: window.location.pathname,
          currentOrgId: window._currentOrgId,
          userStateOrgId: window._userState?.currentOrgId,
          lastPagePerOrg: localStorage.getItem("last-page-per-org"),
        }));
        console.log("FAIL_DIAG", JSON.stringify(diag));
        console.log("REQUESTS_SEEN", JSON.stringify(projectsRequests));
        console.log(
          "ORG_IDS",
          JSON.stringify({
            start: fx.orgStartId,
            a: fx.orgAId,
            b: fx.orgBId,
            c: fx.orgCId,
          })
        );
        console.log(
          "PAGE_IDS",
          JSON.stringify({
            start: fx.pageStartId,
            a: fx.pageAId,
            b: fx.pageBId,
            c: fx.pageCId,
          })
        );
        console.log("CONSOLE_NAV", JSON.stringify(consoleNav));
        console.log("CONSOLE_ERRORS", JSON.stringify(consoleErrors));
        throw e;
      }

      // The switcher trigger must reflect Org C — pins M-2 in the
      // rapid-switch form (label fans out via hyperclast:current-org-changed
      // when setCurrentOrgId is called, regardless of which switch ends
      // up "winning" the seq guard).
      await expect(page.locator(".org-switcher-trigger")).toHaveText(new RegExp(fx.orgCName, "i"), {
        timeout: 10000,
      });

      // The sidenav must show Org C's project/page — NOT A's or B's. We
      // assert by page title since each org has exactly one distinctly
      // titled page.
      await page.waitForFunction(
        ({ cTitle, aTitle, bTitle }) => {
          const titles = Array.from(document.querySelectorAll(".page-title"))
            .map((el) => (el.textContent || "").trim())
            .filter(Boolean);
          const joined = titles.join("|");
          return joined.includes(cTitle) && !joined.includes(aTitle) && !joined.includes(bTitle);
        },
        { cTitle: fx.pageCTitle, aTitle: fx.pageATitle, bTitle: fx.pageBTitle },
        { timeout: 15000 }
      );

      // Three switches → three outbound `projects/?org_id=...` requests
      // (Start's was already done at login and pre-route; we counted only
      // post-route ones). Filter by the three target org ids to be
      // robust against any unrelated traffic.
      const targetOrgIds = new Set([fx.orgAId, fx.orgBId, fx.orgCId]);
      const targetRequests = projectsRequests.filter((url) => {
        const u = new URL(url);
        return targetOrgIds.has(u.searchParams.get("org_id"));
      });
      const requestedOrgIds = targetRequests.map((url) => new URL(url).searchParams.get("org_id"));
      expect(requestedOrgIds).toContain(fx.orgAId);
      expect(requestedOrgIds).toContain(fx.orgBId);
      expect(requestedOrgIds).toContain(fx.orgCId);
      // We don't pin the exact count (Svelte effects can re-fetch on
      // currentOrgId churn in pathological cases), but the must-have
      // invariant is "all three appeared in the wire".

      // No console errors from superseded switches.
      expect(consoleErrors).toEqual([]);

      await ctx.close();
    } finally {
      cleanupFixture(fx.userId);
    }
  });
});
