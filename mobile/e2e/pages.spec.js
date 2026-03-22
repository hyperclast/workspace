const { test, expect } = require("@playwright/test");
const { navigateAuthenticated } = require("./helpers");

test.describe("Page view", () => {
  test("renders page content as markdown", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-1");

    await expect(page.getByText("Welcome to the project")).toBeVisible();
    await expect(page.getByText("Follow these steps to get started")).toBeVisible();
  });

  test("shows edit button when user is page owner", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-1");

    await expect(page.getByTestId("edit-button")).toBeVisible();
  });

  test("hides edit button when user is not owner", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-2");

    await expect(page.getByText("Overview of the system")).toBeVisible();
    await expect(page.getByTestId("edit-button")).not.toBeVisible();
  });

  test("shows error for non-existent page", async ({ page }) => {
    // Override the mock to return 404 for this specific page
    await navigateAuthenticated(page, "/page/nonexistent", {
      pages: { nonexistent: null },
    });

    await expect(page.getByText("Page not found")).toBeVisible();
  });
});

test.describe("Page edit", () => {
  test("loads page content into editor fields", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-1");

    await page.getByTestId("edit-button").click();

    await expect(page.getByTestId("title-input")).toHaveValue("Getting Started");
    await expect(page.getByTestId("content-input")).toContainText("Welcome to the project");
  });

  test("save updates page and navigates back", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-1");

    await page.getByTestId("edit-button").click();
    await expect(page.getByTestId("title-input")).toBeVisible();

    // Edit title
    await page.getByTestId("title-input").fill("Updated Title");
    await page.getByTestId("save-button").click();

    // Should navigate back to page view
    await expect(page.getByTestId("title-input")).not.toBeVisible();
  });

  test("edit button navigates to edit screen", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-1");

    await page.getByTestId("edit-button").click();

    await expect(page.getByTestId("title-input")).toBeVisible();
    await expect(page.getByTestId("content-input")).toBeVisible();
    await expect(page.getByTestId("save-button")).toBeVisible();
  });
});

test.describe("Page create", () => {
  test("FAB creates page and opens editor", async ({ page }) => {
    await navigateAuthenticated(page);

    await page.getByText("Project Alpha").click();
    await expect(page.getByText("Getting Started")).toBeVisible();

    await page.getByTestId("fab-new-page").click();

    // Should navigate to the new page's edit screen
    await expect(page.getByTestId("title-input")).toBeVisible();
  });
});
