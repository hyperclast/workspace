const { test, expect } = require("@playwright/test");
const { mockApi, navigateAuthenticated, setupAuth } = require("./helpers");

test.describe("Authentication", () => {
  test("redirects unauthenticated user to login", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByText("Sign in to continue")).toBeVisible();
    await expect(page.getByPlaceholder("Email")).toBeVisible();
  });

  test("login with valid credentials shows home screen", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await page.getByPlaceholder("Email").fill("test@example.com");
    await page.getByPlaceholder("Password").fill("password123");
    await page.getByText("Sign in", { exact: true }).click();

    await expect(page.getByText("Project Alpha")).toBeVisible();
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    await mockApi(page, {
      loginError: { status: 400, data: { flows: [{}] } },
    });
    await page.goto("/");

    await page.getByPlaceholder("Email").fill("wrong@example.com");
    await page.getByPlaceholder("Password").fill("bad");
    await page.getByText("Sign in", { exact: true }).click();

    // The login screen shows the error message from the catch block
    await expect(page.getByText(/Login failed|Invalid/i)).toBeVisible();
  });

  test("login validates empty fields before API call", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await page.getByText("Sign in", { exact: true }).click();

    await expect(page.getByText("Enter your email and password")).toBeVisible();
  });

  test("toggle between sign in and sign up", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByText("Sign in to continue")).toBeVisible();

    await page.getByText("Need an account? Sign up").click();
    await expect(page.getByText("Create an account")).toBeVisible();
    await expect(page.getByText("Sign up", { exact: true }).first()).toBeVisible();

    await page.getByText("Already have an account? Sign in").click();
    await expect(page.getByText("Sign in to continue")).toBeVisible();
  });

  test("sign up with valid credentials shows home screen", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await page.getByText("Need an account? Sign up").click();
    await page.getByPlaceholder("Email").fill("new@example.com");
    await page.getByPlaceholder("Password").fill("password123");
    await page.getByText("Sign up", { exact: true }).click();

    await expect(page.getByText("Project Alpha")).toBeVisible();
  });

  test("logout redirects to login", async ({ page }) => {
    await navigateAuthenticated(page);
    await expect(page.getByText("Project Alpha")).toBeVisible();

    // Navigate to Settings tab
    await page.getByRole("tab", { name: /Settings/i }).click();
    await expect(page.getByText("Sign out")).toBeVisible();

    await page.getByText("Sign out").click();

    await expect(page.getByText("Sign in to continue")).toBeVisible();
  });
});
