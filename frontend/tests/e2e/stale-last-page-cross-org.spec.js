/**
 * Scenario C — Stale `last_page_id` cross-org redirect (M-1 pin).
 *
 * The bug class: `Profile.org_state[<orgA>].last_page_id` holds the external
 * id of a page that lives in *Org B*. The user's `Profile.current_org` is
 * Org A. Hitting `/` must NOT silently redirect into Org B; the read path
 * needs to constrain the stored id by `project__org=current_org` and fall
 * through to the in-org newest-page Path 2 when the id doesn't match.
 *
 * This spec provisions a synthetic user with membership in two orgs, plants
 * the cross-org stale pointer via `docker exec`, drives `/` in a fresh
 * browser context, asserts the landed page belongs to Org A, and cleans up.
 *
 * Requires Docker; skips cleanly if the backend container isn't reachable.
 *
 * Run with:
 *   TEST_DOCKER_CONTAINER=backend-hyper-9800-ws-web-1 \
 *     npx playwright test stale-last-page-cross-org.spec.js --reporter=list
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

function provisionStalePointerFixture() {
  const ts = Date.now().toString(36);
  const email = `stale-${ts}@e2e.local`;
  const password = "stale-e2e-pw";

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

org_a = Org.objects.create(name="StaleOrgA-${ts}")
org_b = Org.objects.create(name="StaleOrgB-${ts}")
OrgMember.objects.create(org=org_a, user=user, role=OrgMemberRole.ADMIN.value)
OrgMember.objects.create(org=org_b, user=user, role=OrgMemberRole.ADMIN.value)

proj_a = Project.objects.create(org=org_a, name="ProjA-${ts}", creator=user, org_members_can_access=True)
proj_b = Project.objects.create(org=org_b, name="ProjB-${ts}", creator=user, org_members_can_access=True)

page_a = Page.objects.create(
    project=proj_a, creator=user, title="A-Page-${ts}",
    details={"content": "a-body", "filetype": "md", "schema_version": 1},
)
page_b = Page.objects.create(
    project=proj_b, creator=user, title="B-Page-${ts}",
    details={"content": "b-body", "filetype": "md", "schema_version": 1},
)

# Corrupt: store Org B's page id under the Org A bucket. The read path
# must NOT honor it; it must fall through to Path 2 (newest accessible
# page WITHIN Org A — page_a here).
profile = user.profile
profile.current_org = org_a
profile.org_state = {org_a.external_id: {"last_page_id": page_b.external_id}}
profile.save(update_fields=["current_org", "org_state", "modified"])

print(f"USER_ID={user.id}")
print(f"EMAIL={user.email}")
print(f"PASSWORD=${password}")
print(f"ORG_A_ID={org_a.external_id}")
print(f"ORG_B_ID={org_b.external_id}")
print(f"PAGE_A_ID={page_a.external_id}")
print(f"PAGE_B_ID={page_b.external_id}")
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
  };
}

function cleanupStalePointerFixture(userId) {
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

test.describe("Stale cross-org last_page_id (M-1)", () => {
  test("homepage redirect stays in current_org even when the stored last_page_id points at another org", async ({
    browser,
  }) => {
    test.skip(
      !isDockerContainerAvailable(),
      `Docker container ${DOCKER_CONTAINER} not found — required to seed stale-pointer scenario`
    );

    const fx = provisionStalePointerFixture();
    try {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await page.setViewportSize({ width: 1280, height: 900 });
      await loginAs(page, fx.email, fx.password);

      // Drive the homepage redirect explicitly.
      await page.goto(`${BASE_URL}/`);
      await page.waitForSelector("#editor", { timeout: 20000 });

      // The redirect landed on a /pages/<id>/ URL. The id must be page_a
      // (newest accessible page in org_a — Path 2 fallback), and MUST NOT
      // be page_b (cross-org leakage that Path 1 would have caused).
      const path = await page.evaluate(() => window.location.pathname);
      const match = path.match(/^\/pages\/([^/]+)\/?$/);
      expect(match, `expected /pages/<id>/, got ${path}`).toBeTruthy();
      const landedPageId = match[1];

      expect(
        landedPageId,
        `landed on cross-org page ${landedPageId}; the stale pointer leaked`
      ).not.toBe(fx.pageBId);
      expect(landedPageId).toBe(fx.pageAId);

      // The page-canonical invariant: `window._currentOrgId` follows the
      // open page, so confirming the rune is Org A's id is a second check
      // that the URL truly belongs to Org A and not just shares an external
      // id shape.
      const liveOrgId = await page.evaluate(() => window._currentOrgId);
      expect(liveOrgId).toBe(fx.orgAId);

      await ctx.close();
    } finally {
      cleanupStalePointerFixture(fx.userId);
    }
  });
});
