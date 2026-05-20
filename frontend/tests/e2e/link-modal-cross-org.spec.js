/**
 * Scenario D — LinkModal cross-org autocomplete leak (H-1 pin), UI form.
 *
 * `org-boundary.spec.js` already pins the request-level boundary (the
 * `/api/pages/autocomplete/` URL must carry `org_id` for the active org).
 * This spec is the belt-and-suspenders UI flow: open the LinkModal, type a
 * substring that would match pages in *both* the user's orgs, and confirm:
 *
 *   - The outbound autocomplete request URL carries `org_id=<currentOrg>`.
 *   - The dropdown only renders the current-org matches.
 *
 * Provisioning is via `docker exec`: two synthetic orgs for one user, each
 * with a page whose title shares the same probe-word so a missing `org_id`
 * filter would surface BOTH titles. The current org at test time is
 * page-canonical (set by whichever page Playwright loads first).
 *
 * Run with:
 *   TEST_DOCKER_CONTAINER=backend-hyper-9800-ws-web-1 \
 *     npx playwright test link-modal-cross-org.spec.js --reporter=list
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

function provisionLinkModalFixture() {
  const ts = Date.now().toString(36);
  const email = `lm-${ts}@e2e.local`;
  const password = "lm-e2e-pw";
  // Probe word is unique per run so the dropdown filter is unambiguous and
  // can't accidentally match unrelated dev-DB pages.
  const probe = `LMprobe${ts}`;

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

org_a = Org.objects.create(name="LMOrgA-${ts}")
org_b = Org.objects.create(name="LMOrgB-${ts}")
OrgMember.objects.create(org=org_a, user=user, role=OrgMemberRole.ADMIN.value)
OrgMember.objects.create(org=org_b, user=user, role=OrgMemberRole.ADMIN.value)

proj_a = Project.objects.create(org=org_a, name="LM-ProjA-${ts}", creator=user, org_members_can_access=True)
proj_b = Project.objects.create(org=org_b, name="LM-ProjB-${ts}", creator=user, org_members_can_access=True)

# Two pages with the same probe substring so a missing org_id filter
# would surface BOTH in autocomplete. Page A is the one we'll be ON
# when the LinkModal opens; the test asserts page B's title is NOT
# in the dropdown.
page_a = Page.objects.create(
    project=proj_a, creator=user, title="${probe}-A-page",
    details={"content": "a", "filetype": "md", "schema_version": 1},
)
page_b = Page.objects.create(
    project=proj_b, creator=user, title="${probe}-B-page",
    details={"content": "b", "filetype": "md", "schema_version": 1},
)

user.profile.current_org = org_a
user.profile.org_state = {}
user.profile.save(update_fields=["current_org", "org_state", "modified"])

print(f"USER_ID={user.id}")
print(f"EMAIL={user.email}")
print(f"PASSWORD=${password}")
print(f"ORG_A_ID={org_a.external_id}")
print(f"ORG_B_ID={org_b.external_id}")
print(f"PAGE_A_ID={page_a.external_id}")
print(f"PAGE_B_ID={page_b.external_id}")
print(f"PROBE=${probe}")
print(f"TITLE_A=${probe}-A-page")
print(f"TITLE_B=${probe}-B-page")
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
    orgAId: grab("ORG_A_ID"),
    orgBId: grab("ORG_B_ID"),
    pageAId: grab("PAGE_A_ID"),
    pageBId: grab("PAGE_B_ID"),
    probe: grab("PROBE"),
    titleA: grab("TITLE_A"),
    titleB: grab("TITLE_B"),
  };
}

function cleanupLinkModalFixture(userId) {
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

test.describe("LinkModal cross-org autocomplete (H-1, UI form)", () => {
  test("title-search dropdown scopes to current org and the request carries org_id", async ({
    browser,
  }) => {
    test.skip(
      !isDockerContainerAvailable(),
      `Docker container ${DOCKER_CONTAINER} not found — required to seed LinkModal scenario`
    );

    const fx = provisionLinkModalFixture();
    try {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await page.setViewportSize({ width: 1280, height: 900 });
      await loginAs(page, fx.email, fx.password);

      // Navigate explicitly to Page A so the page-canonical invariant
      // pins `window._currentOrgId` to Org A regardless of where the
      // homepage redirect would have landed.
      await page.goto(`${BASE_URL}/pages/${fx.pageAId}/`);
      await page.waitForSelector("#editor", { timeout: 15000 });
      await page.waitForFunction((orgId) => window._currentOrgId === orgId, fx.orgAId, {
        timeout: 10000,
      });

      // Collect every /api/pages/autocomplete/ request so we can assert that
      // EVERY request from the modal carries org_id — not just the one whose
      // response we await. A partial-prefix request that slipped through
      // without org_id would be the exact H-1 leak this scenario pins.
      const acRequests = [];
      page.on("request", (req) => {
        if (/\/api\/(?:v1\/)?pages\/autocomplete\//.test(req.url())) {
          acRequests.push(req);
        }
      });

      // Open the LinkModal by dispatching `mousedown` on the toolbar button.
      // The button uses `onmousedown={(e) => { e.preventDefault(); item.action(); }}`
      // (Toolbar.svelte:439) — NOT onclick — so Playwright's `.click()` works
      // only because mousedown is part of its event sequence. Dispatching
      // mousedown directly is more reliable and matches the exact event the
      // handler is listening for, with no element-stability poll needed.
      await page.locator('button[title^="Insert link"]').first().dispatchEvent("mousedown");
      await page.waitForSelector(".modal", { timeout: 5000 });
      await page.waitForSelector("#link-url", { timeout: 5000 });

      // Arm the response wait BEFORE dispatching the input event so we don't
      // miss a fast response. Used as a promise — we await it below after
      // dispatching the input so the debouncer + network round-trip completes.
      const fullProbeRespPromise = page.waitForResponse(
        (res) => {
          if (!/\/api\/(?:v1\/)?pages\/autocomplete\//.test(res.url())) return false;
          const u = new URL(res.url());
          return (u.searchParams.get("q") || "").includes(fx.probe);
        },
        { timeout: 10000 }
      );

      // Set the input value and fire one `input` event directly. The Svelte
      // `oninput` handler in LinkModal.svelte calls `fetchSuggestions(value)`
      // after a 150ms debouncer — one dispatchEvent triggers exactly one
      // debounced request with the full probe.
      await page.evaluate((probe) => {
        const input = document.querySelector("#link-url");
        if (!input) throw new Error("link-url input not present");
        input.value = probe;
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }, fx.probe);

      // We use waitForResponse's return value directly because the `page.on
      // ("response", async ...)` listener that pushes to acResponses is not
      // awaited by Playwright — the async body can still be running when
      // waitForResponse resolves, leaving acResponses with one fewer entry
      // than expected at assertion time.
      const fullProbeResp = await fullProbeRespPromise;

      // The H-1 boundary fires at the request-and-response layer: the modal
      // must (a) attach org_id of the currently-open page's org to the URL,
      // and (b) the backend must filter to only Org A pages. We verify both.
      // The existing org-boundary.spec.js pins only (a). This spec adds (b)
      // — asserting that the actual payload the LinkModal would render
      // contains the Org A page and NOT the Org B page. Asserting against
      // the response body (not the DOM dropdown) sidesteps a Svelte $effect
      // race where the LinkModal input element detaches mid-typing.
      expect(acRequests.length).toBeGreaterThan(0);
      for (const req of acRequests) {
        const u = new URL(req.url());
        expect(
          u.searchParams.get("org_id"),
          `every autocomplete request must carry org_id; ${req.url()} did not`
        ).toBe(fx.orgAId);
      }
      const fullProbeUrl = new URL(fullProbeResp.url());
      expect(fullProbeUrl.searchParams.get("org_id")).toBe(fx.orgAId);
      expect(fullProbeUrl.searchParams.get("q")).toContain(fx.probe);
      expect(fullProbeResp.status()).toBe(200);
      const body = await fullProbeResp.json();
      const returnedTitles = (body?.pages || []).map((p) => p.title);
      expect(returnedTitles).toContain(fx.titleA);
      expect(returnedTitles).not.toContain(fx.titleB);

      await ctx.close();
    } finally {
      cleanupLinkModalFixture(fx.userId);
    }
  });
});
