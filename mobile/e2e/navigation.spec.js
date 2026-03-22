const { test, expect } = require("@playwright/test");
const { navigateAuthenticated } = require("./helpers");

test.describe("Tab navigation", () => {
  test("switch between Home, Mentions, and Settings tabs", async ({ page }) => {
    await navigateAuthenticated(page);

    // Home tab is active by default
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();

    // Switch to Mentions via the tab bar (not the heading)
    await page.getByRole("tab", { name: /Mentions/i }).click();
    await expect(page.getByText("Team Updates")).toBeVisible();

    // Switch to Settings
    await page.getByRole("tab", { name: /Settings/i }).click();
    await expect(page.getByText("Account")).toBeVisible();

    // Back to Home
    await page.getByRole("tab", { name: /Home/i }).click();
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });
});

test.describe("Back navigation", () => {
  test("project detail has a header and back navigates to home", async ({ page }) => {
    await navigateAuthenticated(page);

    // Navigate to project detail
    await page.getByText("Project Alpha").click();
    await expect(page.getByText("Getting Started")).toBeVisible();

    // The back button is rendered as a link by React Navigation on web
    await page.getByRole("link", { name: /back/i }).click();

    // Should return to home — check for an element unique to home
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });

  test("page view back navigates to project detail", async ({ page }) => {
    await navigateAuthenticated(page);

    // Home → Project → Page
    await page.getByText("Project Alpha").click();
    await expect(page.getByText("Getting Started")).toBeVisible();

    await page.getByText("Getting Started").click();
    await expect(page.getByText("Welcome to the project")).toBeVisible();

    // Back to project detail
    await page.getByRole("link", { name: /back/i }).click();
    await expect(page.getByText("Architecture Notes")).toBeVisible();
  });

  test("full deep navigation: Home → Project → Page → Edit → back × 3", async ({ page }) => {
    await navigateAuthenticated(page);

    // Home → Project
    await page.getByText("Project Alpha").click();
    await expect(page.getByText("Getting Started")).toBeVisible();

    // Project → Page view
    await page.getByText("Getting Started").click();
    await expect(page.getByText("Welcome to the project")).toBeVisible();

    // Page view → Edit
    await page.getByTestId("edit-button").click();
    await expect(page.getByTestId("title-input")).toBeVisible();

    // Edit → back to Page view
    await page.getByRole("link", { name: /back/i }).click();
    await expect(page.getByTestId("title-input")).not.toBeVisible();
    await expect(page.getByTestId("edit-button")).toBeVisible();

    // Page view → back to Project
    await page.getByRole("link", { name: /back/i }).click();
    await expect(page.getByText("Architecture Notes")).toBeVisible();

    // Project → back to Home
    await page.getByRole("link", { name: /back/i }).click();
    await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  });

  test("direct URL to project detail renders content", async ({ page }) => {
    await navigateAuthenticated(page, "/project/proj-1");

    // Project detail loads with pages
    await expect(page.getByText("Getting Started")).toBeVisible();
    await expect(page.getByText("Architecture Notes")).toBeVisible();
  });

  test("direct URL to page view renders content", async ({ page }) => {
    await navigateAuthenticated(page, "/page/page-1");

    await expect(page.getByText("Welcome to the project")).toBeVisible();
  });
});
