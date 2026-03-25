const { defineConfig } = require("@playwright/test");

const port = process.env.EXPO_WEB_PORT || 8081;
const baseURL = process.env.EXPO_WEB_URL || `http://localhost:${port}`;

module.exports = defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL,
    trace: "on-first-retry",
    video: "retain-on-failure",
    screenshot: "only-on-failure",
  },

  timeout: 30_000,
  expect: { timeout: 10_000 },

  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium", storageState: undefined },
    },
  ],

  webServer: {
    command: `npx expo start --web --port ${port}`,
    url: `http://localhost:${port}`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
