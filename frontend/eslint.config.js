import js from "@eslint/js";
import ts from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";
import { architecturePlugin } from "./tools/architecture.mjs";
export default ts.config(
  {
    ignores: [
      "dist/**",
      "src/routeTree.gen.ts",
      "src/shared/api/generated/schema.d.ts",
      "playwright-report/**",
      "test-results/**",
      "storybook-static/**",
    ],
  },
  js.configs.recommended,
  ...ts.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: { "react-hooks": hooks, architecture: architecturePlugin },
    rules: {
      ...hooks.configs.recommended.rules,
      "architecture/boundaries": "error",
    },
  },
  {
    files: ["**/*.{js,mjs,ts}"],
    languageOptions: {
      globals: { process: "readonly", console: "readonly", URL: "readonly" },
    },
  },
);
