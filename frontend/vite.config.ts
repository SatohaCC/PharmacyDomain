import { defineConfig } from "vitest/config";
import { loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
export default defineConfig(({ mode }) => ({
  plugins: [
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
  ],
  server: {
    proxy: {
      "/api": {
        target:
          loadEnv(mode, process.cwd(), "").API_PROXY_TARGET ||
          "http://127.0.0.1:8000",
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
}));
