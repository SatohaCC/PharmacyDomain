import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";
import { resolve } from "node:path";

const eslint = new ESLint();

describe("依存境界", () => {
  it.each([
    [
      "src/features/corporates/components/ExampleView/ExampleView.tsx",
      'import {api} from "../../../../shared/api/client"; void api;',
    ],
    [
      "src/features/corporates/components/ExampleView/ExampleView.tsx",
      'import type {State} from "./useExample"; export type {State};',
    ],
    [
      "src/features/corporates/model/example.ts",
      'export * from "react";',
    ],
    [
      "src/features/corporates/model/example.ts",
      'export * from "../../../shared/ui/Button";',
    ],
    [
      "src/features/corporates/model/example.ts",
      'export * from "../../../shared/component/Form";',
    ],
    [
      "src/shared/ui/Form/index.ts",
      'export type {FormProps} from "react-aria-components";',
    ],
    [
      "src/shared/ui/Form/index.ts",
      'export * from "react-aria-components";',
    ],
    [
      "src/shared/component/Form/Form.tsx",
      'import {Form} from "react-aria-components"; void Form;',
    ],
    [
      "src/features/corporates/components/ExampleView/ExampleView.tsx",
      'export type {ButtonProps} from "react-aria-components";',
    ],
    [
      "src/features/corporates/components/ExampleView/ExampleView.tsx",
      'import {create} from "@stylexjs/stylex"; void create;',
    ],
    [
      "src/features/corporates/components/Example/Example.tsx",
      'import {api} from "../../../../shared/api/client"; void api;',
    ],
    [
      "src/features/corporates/api/example.ts",
      'export * from "../../stores/api/store-api";',
    ],
    [
      "src/shared/ui/Button/Button.tsx",
      'export * from "../../api/client";',
    ],
    [
      "src/shared/ui/Button/Button.tsx",
      'void import("../../../features/auth/api/session");',
    ],
    [
      "src/shared/ui/Button/Button.tsx",
      'export * from "../../component/Form";',
    ],
    [
      "src/shared/component/Form/Form.tsx",
      'export * from "../../api/client";',
    ],
    [
      "src/shared/component/Form/Form.tsx",
      'void import("../../../features/auth/api/session");',
    ],
    [
      "src/features/corporates/components/Example/Example.tsx",
      'export * from "../../../../routes/admin/route";',
    ],
  ])("%sの禁止参照を検出する", async (file, code) => {
    const [result] = await eslint.lintText(code, { filePath: resolve(file) });
    expect(
      result.messages.some((m) => m.ruleId === "architecture/boundaries"),
    ).toBe(true);
  });

  it("正規の表示部品と型の参照を許可する", async () => {
    const [result] = await eslint.lintText(
      'import {Button} from "../../../../shared/ui/Button"; import {Form} from "../../../../shared/component/Form"; import type {Corporate} from "../../model/corporate"; export const View=({corporate}:{corporate:Corporate})=><Form onSubmit={()=>{}}><Button>{corporate.name}</Button></Form>;',
      {
        filePath: resolve(
          "src/features/corporates/components/ExampleView/ExampleView.tsx",
        ),
      },
    );
    expect(
      result.messages.filter((m) => m.ruleId === "architecture/boundaries"),
    ).toEqual([]);
  });

  it("shared/uiでのライブラリ組み立てと最小名前付き値再エクスポートを許可する", async () => {
    const [uiResult] = await eslint.lintText(
      'import {Button as AriaButton} from "react-aria-components"; import {styles} from "./Button.styles"; export const Button=()=> <AriaButton>{String(Boolean(styles))}</AriaButton>;',
      { filePath: resolve("src/shared/ui/Button/Button.tsx") },
    );
    const [reexportResult] = await eslint.lintText(
      'export { Form as AriaForm } from "react-aria-components";',
      { filePath: resolve("src/shared/ui/Form/index.ts") },
    );
    expect(
      uiResult.messages.filter((m) => m.ruleId === "architecture/boundaries"),
    ).toEqual([]);
    expect(
      reexportResult.messages.filter(
        (m) => m.ruleId === "architecture/boundaries",
      ),
    ).toEqual([]);
  });

  it("shared/componentからshared/uiの参照を許可する", async () => {
    const [result] = await eslint.lintText(
      'import {AriaForm} from "../../ui/Form"; import {Button} from "../../ui/Button"; import {Alert} from "../../ui/Alert"; export const Form=()=> <AriaForm><Alert>x</Alert><Button>ok</Button></AriaForm>;',
      { filePath: resolve("src/shared/component/Form/Form.tsx") },
    );
    expect(
      result.messages.filter((m) => m.ruleId === "architecture/boundaries"),
    ).toEqual([]);
  });
});
