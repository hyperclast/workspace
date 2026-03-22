const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],

  use: {
    baseURL: process.env.EXPO_WEB_URL || "http://localhost:8081",
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

  webServer: undefined,
});
