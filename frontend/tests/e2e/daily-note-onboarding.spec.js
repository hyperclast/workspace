/**
 * End-to-end test for the Daily Note onboarding flow when the user already
 * has a flat "Daily Notes" project full of YYYY-MM-DD titled pages.
 *
 * Flow under test:
 *   1. User lands with an existing "Daily Notes" project and 3 dated pages
 *      sitting at the project root (no year/month folders).
 *   2. User clicks the sidenav calendar icon.
 *   3. Welcome modal tells them that N existing notes will be auto-organized.
 *   4. User clicks "Got it".
 *   5. The 3 existing pages are filed into YYYY/MM folders and today's note
 *      opens.
 *
 * Requires Docker stack running so we can reset state via `manage.py shell`.
 *
 * Run with:
 *   npx playwright test daily-note-onboarding.spec.js --headed
 */

import { test, expect } from "@playwright/test";
import { execSync } from "child_process";

const BASE_URL = process.env.TEST_BASE_URL || "http://localhost:9800";
const TEST_EMAIL = process.env.TEST_EMAIL || "dev@localhost";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "dev";
const DOCKER_CONTAINER =
  process.env.TEST_DOCKER_CONTAINER || "backend-workspace-internal-9800-ws-web-1";

// ---------------------------------------------------------------------------
// Docker / shell helpers
// ---------------------------------------------------------------------------

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
 * Run a Python snippet inside the backend container's Django shell.
 * Returns stdout as a string.
 */
function runShell(script) {
  const cmd = `docker exec -i ${DOCKER_CONTAINER} python manage.py shell`;
  return execSync(cmd, {
    input: script,
    encoding: "utf-8",
    timeout: 30000,
  });
}

/**
 * Reset the test user's daily-note config and hard-delete any "Daily Notes"
 * projects (plus their pages/folders) so the test starts from a clean slate.
 * Then create a fresh "Daily Notes" project with the given flat dated pages.
 *
 * Returns { projectId } — the external_id of the created project.
 */
function seedFlatDailyNotes(dates) {
  const datesJson = JSON.stringify(dates);
  const script = `
import json
from django.contrib.auth import get_user_model
from pages.models import Page, Project, Folder
from users.models import OrgMember

User = get_user_model()
user = User.objects.get(email="${TEST_EMAIL}")

# Reset profile config
profile = user.profile
profile.daily_note_project = None
profile.daily_note_template = None
profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])

# Hard-delete prior "Daily Notes" project(s) for this user so the test is idempotent
for p in Project.objects.filter(creator=user, name="Daily Notes"):
    Page.objects.filter(project=p).delete()
    Folder.objects.filter(project=p).delete()
    p.delete()

membership = OrgMember.objects.filter(user=user).order_by("created").first()
if not membership:
    raise RuntimeError("Test user has no org membership")

project = Project.objects.create(
    org=membership.org,
    name="Daily Notes",
    description="Seeded by daily-note-onboarding e2e test",
    creator=user,
)

dates = ${datesJson}
for d in dates:
    page = Page.objects.create(
        project=project,
        creator=user,
        title=d,
        details={"content": "", "filetype": "md"},
        folder=None,
    )
    page.editors.add(user)

print("RESULT:" + json.dumps({"project_id": project.external_id}))
`;
  const out = runShell(script);
  const line = out
    .split("\n")
    .map((l) => l.trim())
    .find((l) => l.startsWith("RESULT:"));
  if (!line) {
    throw new Error(`Seed script produced unexpected output:\n${out}`);
  }
  return JSON.parse(line.slice("RESULT:".length));
}

/**
 * Clean up seeded state — reset profile config and delete the Daily Notes project.
 */
function cleanup() {
  const script = `
from django.contrib.auth import get_user_model
from pages.models import Page, Project, Folder

User = get_user_model()
user = User.objects.get(email="${TEST_EMAIL}")

profile = user.profile
profile.daily_note_project = None
profile.daily_note_template = None
profile.save(update_fields=["daily_note_project", "daily_note_template", "modified"])

for p in Project.objects.filter(creator=user, name="Daily Notes"):
    Page.objects.filter(project=p).delete()
    Folder.objects.filter(project=p).delete()
    p.delete()
print("CLEANUP_OK")
`;
  runShell(script);
}

// ---------------------------------------------------------------------------
// Browser helpers
// ---------------------------------------------------------------------------

async function login(page) {
  await page.goto(`${BASE_URL}/login`);
  await page.waitForSelector("#login-email", { timeout: 10000 });
  await page.fill("#login-email", TEST_EMAIL);
  await page.fill("#login-password", TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForSelector("#editor", { timeout: 20000 });
}

/**
 * Fetch the full project (with pages + folders) from the API, using the
 * authenticated browser session.
 */
async function fetchProject(page, projectId) {
  return page.evaluate(async (pid) => {
    const res = await fetch(`/api/v1/projects/${pid}?details=full`, {
      credentials: "same-origin",
    });
    if (!res.ok) throw new Error(`GET project failed: ${res.status}`);
    return res.json();
  }, projectId);
}

// ---------------------------------------------------------------------------
// Test
// ---------------------------------------------------------------------------

test.describe("Daily Note onboarding — auto-organize existing notes", () => {
  test.setTimeout(120000);

  test("files flat YYYY-MM-DD pages into year/month folders and opens today's note", async ({
    page,
  }) => {
    test.skip(!isDockerContainerAvailable(), `Docker container ${DOCKER_CONTAINER} not found`);

    // Mix of years and months, including two dates in the same month so we
    // can verify folder reuse (no duplicate YYYY/MM folders get created).
    const existingDates = [
      "2024-11-02",
      "2024-11-30", // same month as above — must share the folder
      "2025-01-15",
      "2025-02-03",
      "2026-03-20",
    ];
    const { project_id: projectId } = seedFlatDailyNotes(existingDates);

    try {
      await login(page);

      // Wait for the app to finish loading — all initial API calls (project
      // list, page data) and JS setup (event handlers) must complete before
      // we interact with the UI.
      await page.waitForLoadState("networkidle", { timeout: 15000 });

      // Calendar icon lives in the sidebar header, always visible when the
      // sidebar is open. Default desktop viewport shows it.
      const calendarBtn = page.locator("#sidebar-daily-note-btn");
      await calendarBtn.waitFor({ state: "visible", timeout: 5000 });

      // Click the calendar and wait for the /today/ API call to confirm the
      // click handler fired. The 409 response triggers the welcome modal flow.
      const [todayResponse] = await Promise.all([
        page.waitForResponse((r) => r.url().includes("/daily-note/today/"), { timeout: 10000 }),
        calendarBtn.click(),
      ]);
      expect(todayResponse.status()).toBe(409);

      // Welcome modal appears after detectWelcomeContext() fetches projects
      const modal = page.locator(".modal").filter({ hasText: "Daily Note" });
      await modal.waitFor({ state: "visible", timeout: 10000 });
      await expect(modal).toContainText("Daily Notes");
      await expect(modal).toContainText(`organize ${existingDates.length} existing notes`);

      // Set up listener for the creation POST /today/ response (200) BEFORE
      // clicking "Got it" so we don't miss it.  The 409 already fired above;
      // the next matching response is the 200 that creates today's note.
      const todayCreationPromise = page.waitForResponse(
        (r) => r.url().includes("/daily-note/today/") && r.status() === 200,
        { timeout: 30000 }
      );

      // Proceed with the default (silent) path
      await modal.locator("button:has-text('Got it')").click();

      // Wait for the creation response — this tells us the exact project and
      // page title the backend used, eliminating date/project mismatches.
      const creationResponse = await todayCreationPromise;
      const creationData = await creationResponse.json();
      const today = creationData.title;
      const verifyProjectId = creationData.project_external_id;

      // The auto-setup should have picked our seeded project.  If it didn't,
      // another "Daily Notes" project was reachable — flag it explicitly.
      expect(
        verifyProjectId,
        `auto-setup used project ${verifyProjectId} instead of seeded ${projectId}`
      ).toBe(projectId);

      // Navigation to today's note — URL changes to /pages/{id}/
      await page.waitForURL(/\/pages\/[A-Za-z0-9]+\//, { timeout: 20000 });

      // Wait for any in-flight navigation/organize calls to settle before
      // probing the API for folder state.
      await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});

      // Verify the editor shows today's note
      await page.waitForSelector(".cm-content", { timeout: 10000 });

      const projectAfter = await fetchProject(page, verifyProjectId);

      // Every seeded YYYY-MM-DD page is now inside a YYYY/MM folder pair
      const foldersByExtId = new Map((projectAfter.folders || []).map((f) => [f.external_id, f]));
      const pagesByTitle = new Map((projectAfter.pages || []).map((p) => [p.title, p]));

      for (const date of existingDates) {
        const pg = pagesByTitle.get(date);
        expect(pg, `expected page ${date} to exist`).toBeTruthy();
        expect(pg.folder_id, `page ${date} should have a folder`).toBeTruthy();

        const monthFolder = foldersByExtId.get(pg.folder_id);
        const [year, month] = date.split("-");
        expect(monthFolder, `month folder missing for ${date}`).toBeTruthy();
        expect(monthFolder.name).toBe(month);

        const yearFolder = foldersByExtId.get(monthFolder.parent_id);
        expect(yearFolder, `year folder missing for ${date}`).toBeTruthy();
        expect(yearFolder.name).toBe(year);
        expect(yearFolder.parent_id).toBeFalsy();
      }

      // And today's newly-created note also lives under its YYYY/MM folder
      const todaysNote = pagesByTitle.get(today);
      const allTitles = (projectAfter.pages || []).map((p) => p.title);
      expect(
        todaysNote,
        `today's note "${today}" not found in project ${verifyProjectId}; pages: [${allTitles.join(
          ", "
        )}]`
      ).toBeTruthy();
      const todayMonthFolder = foldersByExtId.get(todaysNote.folder_id);
      const [tYear, tMonth] = today.split("-");
      expect(todayMonthFolder?.name).toBe(tMonth);
      const todayYearFolder = foldersByExtId.get(todayMonthFolder.parent_id);
      expect(todayYearFolder?.name).toBe(tYear);

      // Folder reuse: the two 2024-11 dates must share a single month folder,
      // not get duplicated into two "11" folders under the same 2024 parent.
      const nov2024FolderIds = new Set([
        pagesByTitle.get("2024-11-02").folder_id,
        pagesByTitle.get("2024-11-30").folder_id,
      ]);
      expect(nov2024FolderIds.size).toBe(1);

      // Cross-check folder cardinality. Existing dates cover years
      // {2024, 2025, 2026} and today contributes another (usually a 4th) year.
      // Count year folders (no parent) and month folders (YYYY under them).
      const expectedYearNames = new Set([...existingDates.map((d) => d.split("-")[0]), tYear]);
      const yearFolders = (projectAfter.folders || []).filter((f) => !f.parent_id);
      const yearNames = new Set(yearFolders.map((f) => f.name));
      for (const y of expectedYearNames) {
        expect(yearNames.has(y), `year folder ${y} should exist`).toBe(true);
      }
      // No duplicate year folders
      expect(yearFolders.length).toBe(yearNames.size);

      // Month folders: one per unique (year, month) across seeded + today's note
      const expectedYearMonth = new Set([
        ...existingDates.map((d) => d.split("-").slice(0, 2).join("-")),
        `${tYear}-${tMonth}`,
      ]);
      const monthFolders = (projectAfter.folders || []).filter((f) => f.parent_id);
      expect(monthFolders.length).toBe(expectedYearMonth.size);
    } finally {
      cleanup();
    }
  });
});
