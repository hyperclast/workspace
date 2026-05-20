/**
 * Scenario G — Per-org daily notes.
 *
 * The daily-note config (project + optional template) is stored per-org in
 * `Profile.org_state[<org>]`. The PATCH and POST endpoints both accept
 * `?org_id=<external_id>` to target a specific workspace. This spec pins:
 *
 *   1. PATCH `/api/v1/users/me/daily-note/config/?org_id=A` writes the
 *      Org A bucket without touching Org B.
 *   2. PATCH `/api/v1/users/me/daily-note/config/?org_id=B` writes the
 *      Org B bucket without disturbing Org A.
 *   3. POST `/api/v1/users/me/daily-note/today/?org_id=A` creates the
 *      dated page under Project A1 (NOT Project B1).
 *   4. POST `/api/v1/users/me/daily-note/today/?org_id=B` creates the
 *      dated page under Project B1.
 *   5. GET `/api/v1/users/me/daily-note/config/?org_id=A|B` returns the
 *      distinct project_external_id per org.
 *
 * Driven entirely through the SPA's authenticated fetch path
 * (page.evaluate + window._csrfToken) so the CSRF and session cookies are
 * the real SPA's — same as profile-persistence.spec.js. The keyboard
 * shortcut Cmd/Ctrl+Alt+D ultimately calls these endpoints, so pinning
 * the endpoints is sufficient.
 *
 * Run with:
 *   TEST_DOCKER_CONTAINER=backend-hyper-9800-ws-web-1 \
 *     npx playwright test per-org-daily-note.spec.js --reporter=list
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

function provisionTwoOrgFixture() {
  const ts = Date.now().toString(36);
  const email = `dn-${ts}@e2e.local`;
  const password = "dn-e2e-pw";

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

org_a = Org.objects.create(name="DNOrgA-${ts}")
org_b = Org.objects.create(name="DNOrgB-${ts}")
OrgMember.objects.create(org=org_a, user=user, role=OrgMemberRole.ADMIN.value)
OrgMember.objects.create(org=org_b, user=user, role=OrgMemberRole.ADMIN.value)

# Distinct projects per org so we can prove the dated page lands in the
# right one. Names include the ts so we don't collide with prior runs.
proj_a = Project.objects.create(org=org_a, name="DN-ProjA-${ts}", creator=user, org_members_can_access=True)
proj_b = Project.objects.create(org=org_b, name="DN-ProjB-${ts}", creator=user, org_members_can_access=True)

# Seed a landing page in Org A so the post-login homepage redirect has
# something to load and the loginAs() helper's #editor selector resolves.
# Without this, _pick_homepage_target returns nothing and we hang on the
# blank dashboard.
Page.objects.create(
    project=proj_a, creator=user, title="DN-Landing-${ts}",
    details={"content": "landing", "filetype": "md", "schema_version": 1},
)

# Pre-pick org_a as current so login lands somewhere sensible.
user.profile.current_org = org_a
user.profile.org_state = {}
user.profile.save(update_fields=["current_org", "org_state", "modified"])

print(f"USER_ID={user.id}")
print(f"EMAIL={user.email}")
print(f"PASSWORD=${password}")
print(f"ORG_A_ID={org_a.external_id}")
print(f"ORG_B_ID={org_b.external_id}")
print(f"PROJ_A_ID={proj_a.external_id}")
print(f"PROJ_B_ID={proj_b.external_id}")
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
    projAId: grab("PROJ_A_ID"),
    projBId: grab("PROJ_B_ID"),
  };
}

function cleanupDailyNoteFixture(userId) {
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

test.describe("Per-org daily-note config", () => {
  test("PATCH/POST scoped by ?org_id route to the right project per org", async ({ browser }) => {
    test.skip(
      !isDockerContainerAvailable(),
      `Docker container ${DOCKER_CONTAINER} not found — required to seed per-org daily-note scenario`
    );

    const fx = provisionTwoOrgFixture();
    try {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await page.setViewportSize({ width: 1280, height: 900 });
      await loginAs(page, fx.email, fx.password);

      // Step 1+2: set per-org config via PATCH for both orgs.
      const patchResults = await page.evaluate(async ({ orgAId, orgBId, projAId, projBId }) => {
        const csrf = window._csrfToken;
        const headers = { "Content-Type": "application/json", "X-CSRFToken": csrf || "" };
        const patchA = await fetch(`/api/v1/users/me/daily-note/config/?org_id=${orgAId}`, {
          method: "PATCH",
          credentials: "include",
          headers,
          body: JSON.stringify({ project_external_id: projAId }),
        });
        const patchB = await fetch(`/api/v1/users/me/daily-note/config/?org_id=${orgBId}`, {
          method: "PATCH",
          credentials: "include",
          headers,
          body: JSON.stringify({ project_external_id: projBId }),
        });
        return {
          patchA: { status: patchA.status, body: await patchA.json() },
          patchB: { status: patchB.status, body: await patchB.json() },
        };
      }, fx);
      expect(patchResults.patchA.status).toBe(200);
      expect(patchResults.patchB.status).toBe(200);

      // Step 5: GET config per org and confirm distinct projects.
      const configResults = await page.evaluate(async ({ orgAId, orgBId }) => {
        const headers = { "Content-Type": "application/json" };
        const getA = await fetch(`/api/v1/users/me/daily-note/config/?org_id=${orgAId}`, {
          credentials: "include",
          headers,
        });
        const getB = await fetch(`/api/v1/users/me/daily-note/config/?org_id=${orgBId}`, {
          credentials: "include",
          headers,
        });
        return {
          getA: { status: getA.status, body: await getA.json() },
          getB: { status: getB.status, body: await getB.json() },
        };
      }, fx);
      expect(configResults.getA.status).toBe(200);
      expect(configResults.getB.status).toBe(200);
      // GET /config/ returns DailyNoteConfigOut: {project: {external_id, name}, ...}
      // — NOT a flat project_external_id like /today/ does. The two endpoints
      // share the "project" concept but emit it in different shapes.
      expect(configResults.getA.body.project?.external_id).toBe(fx.projAId);
      expect(configResults.getB.body.project?.external_id).toBe(fx.projBId);
      expect(configResults.getA.body.project?.external_id).not.toBe(
        configResults.getB.body.project?.external_id
      );

      // Step 3+4: POST /today/ with explicit per-org scoping and confirm the
      // dated page lands in the correct project. The endpoint returns the
      // created page's `project_external_id`.
      const todayResults = await page.evaluate(async ({ orgAId, orgBId }) => {
        const csrf = window._csrfToken;
        const headers = { "Content-Type": "application/json", "X-CSRFToken": csrf || "" };
        const today = (() => {
          const n = new Date();
          return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, "0")}-${String(
            n.getDate()
          ).padStart(2, "0")}`;
        })();
        const todayA = await fetch(`/api/v1/users/me/daily-note/today/?org_id=${orgAId}`, {
          method: "POST",
          credentials: "include",
          headers,
          body: JSON.stringify({ date: today }),
        });
        const todayB = await fetch(`/api/v1/users/me/daily-note/today/?org_id=${orgBId}`, {
          method: "POST",
          credentials: "include",
          headers,
          body: JSON.stringify({ date: today }),
        });
        return {
          todayA: { status: todayA.status, body: await todayA.json() },
          todayB: { status: todayB.status, body: await todayB.json() },
        };
      }, fx);

      expect(todayResults.todayA.status).toBe(200);
      expect(todayResults.todayB.status).toBe(200);
      expect(todayResults.todayA.body.project_external_id).toBe(fx.projAId);
      expect(todayResults.todayB.body.project_external_id).toBe(fx.projBId);
      // Same date → same title format, but DIFFERENT pages (because the
      // backing project is different — uniqueness is per-project).
      expect(todayResults.todayA.body.external_id).not.toBe(todayResults.todayB.body.external_id);

      await ctx.close();
    } finally {
      cleanupDailyNoteFixture(fx.userId);
    }
  });
});
