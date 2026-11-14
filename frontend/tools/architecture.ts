import path from "node:path";

interface ImportExportNode {
  type: string;
  exportKind?: string;
  source?: { value?: unknown } | null;
  specifiers?: { exportKind?: string }[];
}

interface RuleContext {
  filename: string;
  report: (descriptor: {
    node: ImportExportNode;
    messageId: string;
    data: { reason: string };
  }) => void;
}

const normal = (value: string): string => value.replaceAll("\\", "/");
const libraryPattern = /^(react-aria(?:-components)?|@react-aria\/|@stylexjs\/)/;

export function violation(filename: string, source: string): string | undefined {
  const file = normal(filename);
  const target = source.startsWith(".")
    ? normal(path.resolve(path.dirname(filename), source))
    : source;
  const feature = file.match(/\/src\/features\/([^/]+)\//)?.[1];
  const targetFeature = target.match(/\/src\/features\/([^/]+)\//)?.[1];

  if (
    file.includes("/src/") &&
    !file.includes("/src/shared/ui/") &&
    /^(react-aria(?:-components)?|@react-aria\/)/.test(source)
  ) {
    return "React Ariaはshared/ui内部でのみ使用してください。";
  }

  if (
    file.includes("/src/") &&
    !/\/src\/shared\/(?:ui|component|theme)\//.test(file) &&
    /^@stylexjs\//.test(source)
  ) {
    return "StyleXはshared/ui・shared/component・shared/theme内部でのみ使用してください。";
  }

  if (
    file.includes("/src/shared/ui/") &&
    /\/src\/(?:features|app|routes|shared\/(?:api|component))\//.test(target)
  ) {
    return "shared/uiから業務・通信・配線・shared/componentを参照できません。";
  }

  if (
    /\/src\/shared\/(?:component|theme)\//.test(file) &&
    /\/src\/(?:features|app|routes|shared\/api)\//.test(target)
  ) {
    return "共通表示部品・テーマから業務・通信・配線を参照できません。";
  }

  if (feature && /\/src\/(?:routes|app)\//.test(target)) {
    return "機能からルートや配線を参照できません。";
  }

  if (feature && targetFeature && feature !== targetFeature) {
    return "機能同士の直接参照は禁止です。必要な契約を配線から渡してください。";
  }

  if (
    file.includes("/model/") &&
    feature &&
    (/^(react(?:-dom)?(?:\/|$)|@tanstack\/|oidc-client-ts|openapi-fetch)/.test(
      source,
    ) ||
      /\/src\/(?:shared\/(?:api|ui|component|theme)|features\/[^/]+\/(?:api|components|hooks|ui))(?:\/|$)/.test(
        target,
      ) ||
      /\/shared\/(?:forms\/use-|navigation\/leaving)/.test(target))
  ) {
    return "モデルはReact・通信・画面の実装に依存できません。";
  }

  if (
    /(?:-view|View)\.tsx$/.test(file) &&
    (/\/api(?:\/|$)/.test(target) ||
      /\/use(?:-[^/]+|[A-Z][^/]*)(?:\.[cm]?[jt]sx?)?$/.test(target) ||
      source === "@tanstack/react-router" ||
      target.includes("/shared/forms/submission-form"))
  ) {
    return "viewは表示用の契約を受け取り、通信・hook・Routerに依存しません。";
  }

  if (
    feature &&
    /\/(?:components|hooks|ui)\//.test(file) &&
    target.includes("/shared/api/client")
  ) {
    return "通信呼出しは機能のapiアダプタを経由してください。";
  }

  return undefined;
}

function isAllowedAriaReexport(
  filename: string,
  node: ImportExportNode,
  sourceValue: string,
): boolean {
  return (
    node.type === "ExportNamedDeclaration" &&
    node.exportKind !== "type" &&
    !node.specifiers?.some((specifier) => specifier.exportKind === "type") &&
    sourceValue === "react-aria-components" &&
    /\/src\/shared\/ui\/[^/]+\/index\.ts$/.test(normal(filename))
  );
}

export const architecturePlugin = {
  rules: {
    boundaries: {
      meta: {
        type: "problem",
        schema: [],
        messages: { boundary: "{{reason}}" },
      },
      create(context: RuleContext) {
        const check = (node: ImportExportNode) => {
          const source =
            node.source ||
            (node.type === "ImportExpression" ? node.source : undefined);
          if (typeof source?.value !== "string") return;

          const libraryExport =
            node.type.startsWith("Export") && libraryPattern.test(source.value);

          const reason =
            libraryExport &&
            !isAllowedAriaReexport(context.filename, node, source.value)
              ? "ライブラリの型や部品を直接再エクスポートせず、shared/uiの最小名前付き値ラッパー経由で公開してください。"
              : violation(context.filename, source.value);

          if (reason) {
            context.report({ node, messageId: "boundary", data: { reason } });
          }
        };

        return {
          ImportDeclaration: check,
          ExportNamedDeclaration: check,
          ExportAllDeclaration: check,
          ImportExpression: check,
        };
      },
    },
  },
};
