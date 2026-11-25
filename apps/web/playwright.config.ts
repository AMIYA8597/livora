import { defineConfig, devices } from "@playwright/test";

/**
 * Browser journeys against a running stack: the web app at E2E_BASE_URL and the API it points
 * at, on a database loaded with `database/seeds/seed.py`. CI starts both (see ci.yml, "e2e");
 * locally, run `pnpm dev` and the API first. Every journey runs on a desktop and a phone viewport.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // Two everywhere: more parallel browsers starve `next start` on a laptop, and journeys time
  // out on navigations the server hasn't answered yet.
  workers: 2,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
