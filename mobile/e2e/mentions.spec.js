const { test, expect } = require("@playwright/test");
const { navigateAuthenticated } = require("./helpers");

test.describe("Mentions tab", () => {
  test("shows mentions with page title and project name", async ({ page }) => {
    await navigateAuthenticated(page);

    await page.getByRole("tab", { name: /Mentions/i }).click();

    await expect(page.getByText("Team Updates")).toBeVisible();
  });

  test("shows empty state when no mentions", async ({ page }) => {
    await navigateAuthenticated(page, "/", { mentions: { mentions: [] } });

    await page.getByRole("tab", { name: /Mentions/i }).click();

    await expect(page.getByText("No mentions yet")).toBeVisible();
  });

  test("tapping mention navigates to page view", async ({ page }) => {
    await navigateAuthenticated(page);

    await page.getByRole("tab", { name: /Mentions/i }).click();
    await page.getByText("Team Updates").click();

    // page-1 is used for the mention's page_external_id in helpers
    await expect(page.getByText("Welcome to the project")).toBeVisible();
  });
});
