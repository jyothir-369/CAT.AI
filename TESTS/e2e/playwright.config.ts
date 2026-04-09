import { defineConfig, devices } from "@playwright/test";

/**
 * CAT AI — Playwright E2E test configuration.
 * Runs against staging (or local dev via BASE_URL env var).
 */
export default defineConfig({
  testDir: "./",
  testMatch: "**/*.spec.ts",

  /* Maximum time one test can run */
  timeout: 30_000,

  /* Fail fast in CI */
  retries: process.env.CI ? 2 : 0,

  /* Parallel workers */
  workers: process.env.CI ? 2 : 4,

  /* Reporter */
  reporter: [
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["list"],
  ],

  use: {
    /* Base URL from env (staging) or localhost */
    baseURL: process.env.BASE_URL ?? "http://localhost:3000",

    /* Collect trace on failure */
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",

    /* Always use chromium in CI for speed */
    ...devices["Desktop Chrome"],
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    ...(process.env.CI
      ? []
      : [
          {
            name: "firefox",
            use: { ...devices["Desktop Firefox"] },
          },
          {
            name: "mobile-chrome",
            use: { ...devices["Pixel 5"] },
          },
        ]),
  ],
});