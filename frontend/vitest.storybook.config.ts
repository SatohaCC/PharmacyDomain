import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";
import { playwright } from "@vitest/browser-playwright";
import stylex from "@stylexjs/unplugin";
export default defineConfig({
  plugins: [
    stylex.vite({ useCSSLayers: true }),
    storybookTest({
      configDir: fileURLToPath(new URL("./.storybook", import.meta.url)),
    }),
  ],
  test: {
    name: "storybook",
    testTimeout: 15000,
    browser: {
      enabled: true,
      headless: true,
      provider: playwright(),
      instances: [{ browser: "chromium" }],
    },
  },
});
