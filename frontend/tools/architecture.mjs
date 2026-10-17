import path from "node:path";
const normal = (value) => value.replaceAll("\\", "/");
export function violation(filename, source) {
  const file = normal(filename);
  const target = source.startsWith(".")
    ? normal(path.resolve(path.dirname(filename), source))
    : source;
  const feature = file.match(/\/src\/features\/([^/]+)\//)?.[1];
  const targetFeature = target.match(/\/src\/features\/([^/]+)\//)?.[1];
  if (
    file.includes("/src/") &&
    !file.includes("/src/shared/ui/") &&
    /^(react-aria(?:-components)?|@react-aria\/|@stylexjs\/)/.test(source)
  )
    return "UIライブラリはshared/ui内部で使用してください。";
  if (
    file.includes("/src/shared/ui/") &&
    /\/src\/(features|app|routes|shared\/api)\//.test(target)
  )
    return "共通UIから業務・通信・配線を参照できません。";
  if (
    file.includes("/src/shared/api/") &&
    /\/src\/(features|app|routes)\//.test(target)
  )
    return "通信基盤は認証や機能の実装を参照できません。";
  if (feature && /\/src\/(routes|app)\//.test(target))
    return "機能からルートや配線を参照できません。";
  if (feature && targetFeature && feature !== targetFeature)
    return "機能同士の直接参照は禁止です。必要な契約を配線から渡してください。";
  if (
    file.includes("/model/") &&
    feature &&
    (/^(react(?:-dom)?(?:\/|$)|@tanstack\/|oidc-client-ts|openapi-fetch)/.test(
      source,
    ) ||
      /\/src\/(shared\/(api|ui)|features\/[^/]+\/(api|ui))\//.test(target) ||
      /\/shared\/(forms\/use-|navigation\/leaving)/.test(target))
  )
    return "モデルはReact・通信・画面の実装に依存できません。";
  if (
    /-view\.tsx$/.test(file) &&
    (/\/api\//.test(target) ||
      /\/use-[^/]+$/.test(target) ||
      source === "@tanstack/react-router" ||
      target.includes("/shared/forms/submission-form"))
  )
    return "viewは表示用の契約を受け取り、通信・hook・Routerに依存しません。";
  if (feature && file.includes("/ui/") && target.includes("/shared/api/client"))
    return "通信呼出しは機能のapiアダプタを経由してください。";
  return undefined;
}
export const architecturePlugin = {
  rules: {
    boundaries: {
      meta: {
        type: "problem",
        schema: [],
        messages: { boundary: "{{reason}}" },
      },
      create(context) {
        const check = (node) => {
          const source =
            node.source ||
            (node.type === "ImportExpression" ? node.source : undefined);
          if (typeof source?.value !== "string") return;
          const libraryExport = node.type.startsWith("Export") && /^(react-aria(?:-components)?|@react-aria\/|@stylexjs\/)/.test(source.value);
          const reason = libraryExport ? "ライブラリの型や部品を直接再エクスポートせず、独自のUI契約を定義してください。" : violation(context.filename, source.value);
          if (reason)
            context.report({ node, messageId: "boundary", data: { reason } });
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
