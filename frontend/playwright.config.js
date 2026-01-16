import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false, // Run sequentially for timing tests
  forbidOnly: !!process.env.CI,
  retries: 0, // No retries for performance tests
  workers: 1, // Single worker for consistent timing
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL: process.env.TEST_BASE_URL || "http://localhost:9800",
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  // Visual regression snapshot settings
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2,
      animations: "disabled",
    },
  },

  projects: [
    {
      name: "chromium",
      use: {
        browserName: "chromium",
        // Use a clean context each time
        storageState: undefined,
      },
      // Exclude visual regression tests from default project
      testIgnore: "**/visual-regression/**",
    },
    {
      name: "visual-regression",
      testMatch: "**/visual-regression/**/*.spec.js",
      use: {
        browserName: "chromium",
        storageState: undefined,
        // Consistent viewport for visual tests
        viewport: { width: 1280, height: 800 },
        // Disable animations for stable screenshots
        reducedMotion: "reduce",
        // Consistent pixel ratio
        deviceScaleFactor: 1,
      },
    },
  ],

  // Don't start servers automatically - expect them to be running
  webServer: undefined,
});
