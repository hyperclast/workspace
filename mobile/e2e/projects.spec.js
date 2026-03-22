const { test, expect } = require("@playwright/test");
const { navigateAuthenticated } = require("./helpers");

test.describe("Home — project list", () => {
  test("shows projects with page counts", async ({ page }) => {
    await navigateAuthenticated(page);

    await expect(page.getByText("Project Alpha")).toBeVisible();
    await expect(page.getByText("First test project")).toBeVisible();
    await expect(page.getByText("2 pages")).toBeVisible();

    await expect(page.getByText("Project Beta")).toBeVisible();
    await expect(page.getByText("0 pages")).toBeVisible();
  });

  test("shows org section headers when multiple orgs", async ({ page }) => {
    await navigateAuthenticated(page);

    // Two orgs: Acme Corp and Beta Inc
    await expect(page.getByText("Acme Corp")).toBeVisible();
    await expect(page.getByText("Beta Inc")).toBeVisible();
  });

  test("hides org headers when single org", async ({ page }) => {
    const singleOrgProjects = [
      {
        external_id: "proj-1",
        name: "Project Alpha",
        description: null,
        org: { external_id: "org-1", name: "Acme Corp" },
        pages: [],
        files: [],
      },
      {
        external_id: "proj-3",
        name: "Project Gamma",
        description: null,
        org: { external_id: "org-1", name: "Acme Corp" },
        pages: [],
        files: [],
      },
    ];
    await navigateAuthenticated(page, "/", { projects: singleOrgProjects });

    await expect(page.getByText("Project Alpha")).toBeVisible();
    await expect(page.getByText("Project Gamma")).toBeVisible();
    await expect(page.getByText("Acme Corp")).not.toBeVisible();
  });

  test("shows empty state", async ({ page }) => {
    await navigateAuthenticated(page, "/", { projects: [] });

    await expect(page.getByText("No projects yet")).toBeVisible();
  });
});

test.describe("Project detail", () => {
  test("shows pages sorted by most recent", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Project Alpha").click();

    // "Getting Started" (Mar 22) should appear before "Architecture Notes" (Mar 21)
    const titles = page.getByText(/Getting Started|Architecture Notes/);
    await expect(titles.first()).toHaveText("Getting Started");
    await expect(titles.last()).toHaveText("Architecture Notes");
  });

  test("shows empty state for project with no pages", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Project Beta").click();

    await expect(page.getByText("No pages yet")).toBeVisible();
  });

  test("tapping page navigates to page view", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Project Alpha").click();
    await page.getByText("Getting Started").click();

    await expect(page.getByText("Welcome to the project")).toBeVisible();
  });
});
