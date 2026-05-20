/**
 * External collaborator persisted `current_org` survives a fresh session.
 *
 * Page-canonical invariant test (gap §8.16; depends on the M-3 fix in Step 4).
 *
 * Scenario: user X is a project editor in Org B but NOT an OrgMember of
 * Org B. They PATCH `/api/v1/users/me/` with `current_org_id = <Org B>`.
 * In a brand-new browser context (no client-side state to lean on) they
 * log in and visit `/`. The homepage redirect must respect their persisted
 * selection — landing in Org B's content rather than silently falling back
 * to "global newest accessible page" (the pre-fix symptom of the asymmetric
 * read path that gated on `OrgMember` while the write path accepted
 * three-tier access).
 *
 * Requires docker exec into the backend container to seed: the dev user
 * isn't an external collaborator of any synthetic org, and we don't want
 * to mutate the dev user's relationships across runs. Skips cleanly when
 * the container isn't reachable, matching the convention used by
 * `apply-suggestion.spec.js` etc.
 *
 * Run with:
 *   npx playwright test external-collaborator-current-org.spec.js --reporter=list
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

/**
 * Provision an external-collaborator scenario in the backend:
 *   - Org B owned by a synthetic owner (so the dev user is unrelated to it)
 *   - One Project in Org B with one Page
 *   - User X (`external@e2e.local`-style) with NO OrgMember row for Org B
 *   - ProjectEditor row giving X `editor` access to Org B's project
 *
 * Returns `{ orgId, pageId, externalEmail, externalPassword }`. Uses a
 * timestamp suffix so re-runs against a persistent dev DB don't collide.
 *
 * The script is intentionally idempotent on the user side (`get_or_create`)
 * — if a previous test run left rows behind, this run reuses the users and
 * just adds another (Org, Project, Page, ProjectEditor) tuple. The dev DB
 * accumulates synthetic rows over time; clean it manually if it gets noisy.
 */
function provisionExternalCollaborator() {
  const ts = Date.now().toString(36);
  const ownerEmail = `owner-${ts}@e2e.local`;
  const externalEmail = `ext-${ts}@e2e.local`;
  const externalPassword = "ext-e2e-pw";
  const orgName = `ExtOrg-${ts}`;
  const projectName = `ExtProject-${ts}`;
  const pageTitle = `Ext Page ${ts}`;

  // The script must print `KEY=value` lines for every datum the test reads.
  // We grep them out below instead of trying to parse arbitrary stdout.
  const py = `
from allauth.account.models import EmailAddress
from users.models import User, Org, OrgMember
from users.constants import OrgMemberRole
from pages.models import Project, Page, ProjectEditor
from pages.constants import ProjectEditorRole

owner, _ = User.objects.get_or_create(
    username="${ownerEmail}", defaults={"email": "${ownerEmail}"}
)
owner.set_password("owner-e2e-pw")
owner.email = "${ownerEmail}"
owner.save()

org = Org.objects.create(name="${orgName}")
OrgMember.objects.create(org=org, user=owner, role=OrgMemberRole.ADMIN.value)
project = Project.objects.create(
    org=org, name="${projectName}", creator=owner, org_members_can_access=True
)
page = Page.objects.create(
    project=project,
    creator=owner,
    title="${pageTitle}",
    details={"content": "ext-page-body", "filetype": "md", "schema_version": 1},
)

external, _ = User.objects.get_or_create(
    username="${externalEmail}", defaults={"email": "${externalEmail}"}
)
external.set_password("${externalPassword}")
external.email = "${externalEmail}"
external.save()

# allauth gates login on a verified EmailAddress row. Without this the
# login form redirects to the "Almost there! check your inbox" page and
# the SPA #editor never mounts. See backend/users/migrations/
# 0016_ensure_dev_user_verified_email.py for the equivalent dev-user seed.
EmailAddress.objects.update_or_create(
    user=external,
    email="${externalEmail}",
    defaults={"verified": True, "primary": True},
)

ProjectEditor.objects.create(
    project=project, user=external, role=ProjectEditorRole.EDITOR.value
)

# Defensive: the asymmetry under test is read-gates-on-OrgMember while
# write-accepts-three-tier. Confirm the external user really is NOT a
# member of Org B so a future signal/factory change doesn't silently
# moot the test.
assert not OrgMember.objects.filter(org=org, user=external).exists(), (
    "external user must not be an OrgMember for this test to be meaningful"
)

print(f"ORG_ID={org.external_id}")
print(f"PAGE_ID={page.external_id}")
print(f"EXTERNAL_EMAIL={external.email}")
print(f"EXTERNAL_PASSWORD=${externalPassword}")
`;
  // Pipe the script via stdin rather than passing it as `-c <quoted>`. Passing
  // a multi-line JSON-stringified blob as a `-c` argument turns embedded
  // newlines into literal backslash-n once the shell strips the outer quotes,
  // and Python then reports `unexpected character after line continuation
  // character`. Stdin sidesteps the shell-quoting layer entirely.
  const stdout = execSync(`docker exec -i ${DOCKER_CONTAINER} python manage.py shell`, {
    encoding: "utf-8",
    timeout: 20000,
    input: py,
  });
  const grab = (key) => {
    const m = stdout.match(new RegExp(`^${key}=(.+)$`, "m"));
    if (!m) throw new Error(`provision script did not emit ${key}; stdout: ${stdout}`);
    return m[1].trim();
  };
  return {
    orgId: grab("ORG_ID"),
    pageId: grab("PAGE_ID"),
    externalEmail: grab("EXTERNAL_EMAIL"),
    externalPassword: grab("EXTERNAL_PASSWORD"),
  };
}

async function loginAs(page, email, password) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", email);
  await page.fill("#login-password", password);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
}

test.describe("External collaborator — persisted current_org", () => {
  test("project editor (non-OrgMember) lands in their persisted current_org on a fresh session", async ({
    browser,
  }) => {
    test.skip(
      !isDockerContainerAvailable(),
      `Docker container ${DOCKER_CONTAINER} not found — required to seed external-collaborator scenario`
    );

    const { orgId, externalEmail, externalPassword } = provisionExternalCollaborator();

    // First context: log in as the external collaborator and persist their
    // current_org. Use the write endpoint directly so the test is
    // deterministic about *whether* the PATCH succeeded — the OrgSwitcher
    // flow also fires it as fire-and-forget, but we don't want this test to
    // race on that path.
    const ctx1 = await browser.newContext();
    const page1 = await ctx1.newPage();
    await page1.setViewportSize({ width: 1280, height: 900 });
    await loginAs(page1, externalEmail, externalPassword);

    const patchStatus = await page1.evaluate(async (targetOrgId) => {
      const csrf = window._csrfToken;
      const res = await fetch("/api/v1/users/me/", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf || "" },
        body: JSON.stringify({ current_org_id: targetOrgId }),
      });
      return res.status;
    }, orgId);
    // 200 here is the M-3-fix proof: pre-fix the write path already accepted
    // three-tier access, so the PATCH succeeded but `get_user_state` later
    // dropped the persisted value at read time. The interesting assertion
    // is below (Context 2).
    expect(patchStatus).toBe(200);
    await ctx1.close();

    // Second context: brand-new browser. No cookies, no localStorage, no
    // window._userState carryover. The homepage redirect (`/`) is the
    // exact path that pre-fix silently fell back to "global newest
    // accessible page" because `_pick_homepage_target` gated Path 2 on
    // OrgMember membership. Post-fix it delegates to
    // `users.access.user_has_org_access`, which honors three-tier access.
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();
    await page2.setViewportSize({ width: 1280, height: 900 });
    await loginAs(page2, externalEmail, externalPassword);

    // The redirect's final destination must be a page IN Org B, not some
    // unrelated page the external user can also access. We assert both:
    //   1. The server-injected snapshot (`window._userState.currentOrgId`)
    //      reflects Org B — proves `get_user_state`'s Priority 2 path
    //      honored the persisted selection.
    //   2. The URL points at a /pages/<id>/ — proves the redirect went
    //      through `_pick_homepage_target` rather than dropping us on a
    //      no-projects placeholder.
    await page2.waitForSelector(".org-switcher-trigger", { timeout: 10000 });
    const seededOrgId = await page2.evaluate(() => window._userState?.currentOrgId);
    expect(seededOrgId).toBe(orgId);

    const path = await page2.evaluate(() => window.location.pathname);
    expect(path).toMatch(/^\/pages\//);

    // The live rune should also match — guards against a regression where
    // the SPA hydrates with a different value than the template injected.
    const liveOrgId = await page2.evaluate(() => window._currentOrgId);
    expect(liveOrgId).toBe(orgId);

    await ctx2.close();
  });
});
