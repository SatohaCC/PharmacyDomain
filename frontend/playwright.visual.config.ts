import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/visual",
  globalTimeout: 120_000,
  timeout: 20_000,
  snapshotPathTemplate: "{testDir}/snapshots/{platform}/{arg}{ext}",
  use: {
    baseURL: "http://127.0.0.1:6007",
    headless: true,
    browserName: "chromium",
    locale: "ja-JP",
    timezoneId: "Asia/Tokyo",
    colorScheme: "light",
    reducedMotion: "reduce",
    viewport: { width: 1280, height: 900 },
  },
  webServer: {
    command: "node scripts/serve-storybook.mjs",
    url: "http://127.0.0.1:6007",
    reuseExistingServer: false,
    gracefulShutdown: { signal: "SIGTERM", timeout: 1000 },
  },
  reporter: "list",
});
