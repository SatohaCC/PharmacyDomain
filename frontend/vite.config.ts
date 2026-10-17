import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import stylex from "@stylexjs/unplugin";
const workspaceRoot = fileURLToPath(new URL("../", import.meta.url));
export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, workspaceRoot, "");
  return {
    envDir: workspaceRoot,
    plugins: [
      tanstackRouter({ target: "react", autoCodeSplitting: true }),
      stylex.vite({
        useCSSLayers: true,
        devMode: process.env.VITEST ? "off" : "full",
      }),
      react(),
    ],
    server: {
      proxy: {
        "/api": {
          target:
            environment.API_PROXY_TARGET ||
            `http://127.0.0.1:${environment.API_PORT || "8000"}`,
          rewrite: (p) => p.replace(/^\/api/, ""),
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./tests/setup.ts"],
      include: ["tests/**/*.test.{ts,tsx}"],
    },
  };
});
