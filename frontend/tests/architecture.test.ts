import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";
import { resolve } from "node:path";
const eslint = new ESLint();
describe("依存境界", () => {
  it.each([
    [
      "src/features/corporates/ui/example-view.tsx",
      'import {api} from "../../../shared/api/client"; void api;',
    ],
    [
      "src/features/corporates/ui/example-view.tsx",
      'import type {State} from "./use-example"; export type {State};',
    ],
    ["src/features/corporates/model/example.ts", 'export * from "react";'],
    ["src/features/corporates/model/example.ts", 'export * from "../../../shared/ui/controls/button";'],
    ["src/shared/ui/controls/example.tsx", 'export type {ButtonProps} from "react-aria-components";'],
    [
      "src/features/corporates/ui/example.tsx",
      'export type {ButtonProps} from "react-aria-components";',
    ],
    [
      "src/features/corporates/ui/example.tsx",
      'import {create} from "@stylexjs/stylex"; void create;',
    ],
    [
      "src/features/corporates/api/example.ts",
      'export * from "../../stores/api/store-api";',
    ],
    ["src/shared/ui/controls/example.tsx", 'export * from "../../api/client";'],
    [
      "src/shared/ui/controls/example.tsx",
      'void import("../../../features/auth/api/session");',
    ],
    [
      "src/features/corporates/ui/example.tsx",
      'export * from "../../../routes/admin/route";',
    ],
  ])("%sの禁止参照を検出する", async (file, code) => {
    const [result] = await eslint.lintText(code, { filePath: resolve(file) });
    expect(
      result.messages.some((m) => m.ruleId === "architecture/boundaries"),
    ).toBe(true);
  });
  it("正規の表示部品と型の参照を許可する", async () => {
    const [result] = await eslint.lintText(
      'import {Button} from "../../../shared/ui/controls/button"; import type {Corporate} from "../model/corporate"; export const View=({corporate}:{corporate:Corporate})=><Button>{corporate.name}</Button>;',
      { filePath: resolve("src/features/corporates/ui/example-view.tsx") },
    );
    expect(
      result.messages.filter((m) => m.ruleId === "architecture/boundaries"),
    ).toEqual([]);
  });
});
