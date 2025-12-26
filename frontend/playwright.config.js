import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // Run sequentially for timing tests
  forbidOnly: !!process.env.CI,
  retries: 0, // No retries for performance tests
  workers: 1, // Single worker for consistent timing
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],

  use: {
    baseURL: process.env.TEST_BASE_URL || 'http://localhost:9800',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: {
        browserName: 'chromium',
        // Use a clean context each time
        storageState: undefined,
      },
    },
  ],

  // Don't start servers automatically - expect them to be running
  webServer: undefined,
});
