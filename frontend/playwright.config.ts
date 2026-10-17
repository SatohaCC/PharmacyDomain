import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
    headless: true,
    trace: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "pnpm dev --port 5173 --strictPort",
        url: "http://127.0.0.1:5173",
        reuseExistingServer: !process.env.CI,
      },
  reporter: "list",
});
