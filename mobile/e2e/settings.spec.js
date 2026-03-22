const { test, expect } = require("@playwright/test");
const { navigateAuthenticated } = require("./helpers");

test.describe("Settings tab", () => {
  test("shows user account info", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Settings").click();

    await expect(page.getByText("Account")).toBeVisible();
    await expect(page.getByText("testuser")).toBeVisible();
    await expect(page.getByText("test@example.com")).toBeVisible();
  });

  test("shows storage usage", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Settings").click();

    await expect(page.getByText("Storage")).toBeVisible();
    // 2097152 bytes = 2 MB
    await expect(page.getByText(/3 files.*2.*MB/)).toBeVisible();
  });

  test("shows devices with current badge", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Settings").click();

    await expect(page.getByText("Devices")).toBeVisible();
    await expect(page.getByText("Chrome Web")).toBeVisible();
    await expect(page.getByText("Current")).toBeVisible();
    await expect(page.getByText("iPhone 15")).toBeVisible();
    await expect(page.getByText("Remove")).toBeVisible();
  });

  test("shows app version and sign out button", async ({ page }) => {
    await navigateAuthenticated(page);
    await page.getByText("Settings").click();

    await expect(page.getByText(/Version/)).toBeVisible();
    await expect(page.getByText("Sign out")).toBeVisible();
  });
});
