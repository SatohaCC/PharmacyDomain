import { createHash } from "node:crypto";

export function acceptanceEvidence(output, runner = "auto") {
  output = output.replace(/\u001b\[[0-9;]*m/g, "");
  const nodeSummary = [...output.matchAll(/^(?:#|✔)\s*tests\s+\d+/gm)].at(-1);
  if ((runner === "node" || runner === "auto") && nodeSummary) {
    output = output.slice(nodeSummary.index);
  } else if (runner === "pytest") {
    const summary = output.split(/\r?\n/).filter((line) => /\b\d+ (?:passed|failed|skipped|xfailed|xpassed)\b/.test(line)).at(-1);
    if (summary) output = summary;
  } else if (runner === "vitest") {
    const summary = output.split(/\r?\n/).filter((line) => /Tests\s+.*(?:\d+\s+passed|\d+\s+failed)/i.test(line)).at(-1);
    if (summary) output = summary;
  }
  const passedPattern = runner === "playwright"
    ? /\b(\d+) passed\b/g
    : runner === "vitest"
      ? /\b(\d+)\s+passed\b/gi
      : /(?:\b(\d+) passed\b|(?:#|✔)\s*pass\s+(\d+))/g;
  const passed = [...output.matchAll(passedPattern)]
    .reduce((total, match) => total + Number(match[1] ?? match[2]), 0);
  const incomplete = [...output.matchAll(/(?:\b(\d+) (?:skipped|xfailed|xpassed|todo)\b|(?:#|✔)\s*(?:skipped|todo)\s+(\d+))/g)]
    .some((match) => Number(match[1] ?? match[2]) > 0);
  return { passed, incomplete };
}

export function failureFeedback(task, status, output = "") {
  if (status === "passed") return null;
  let docs = "docs/development.md";
  const diagnostics = [...new Set(output.replace(/\u001b\[[0-9;]*m/g, "").split(/\r?\n/).flatMap((line, index, lines) => {
    if (/^[A-Z]+\d{3,4}\b/.test(line)) {
      const location = lines.slice(index + 1, index + 4).join("\n").match(/-->\s+(.+?):\d+:\d+/);
      if (location) return [`${location[1].replaceAll("\\", "/")}: ${line.trim()}`];
    }
    const failed = line.match(/(?:FAILED\s+)([^\s]+::[^\s]+)(?:\s+-\s+(.+))?/);
    if (failed) return [failed[1] + (failed[2] ? ` - ${failed[2]}` : "")];
    const node = line.match(/^\s*(?:✖\s+|not ok \d+ - )(.+?)(?:\s+\([\d.]+m?s\))?$/);
    if (node && !/^(failing tests|tests \d+)/.test(node[1])) return [node[1]];
    const exception = line.match(/^\s*((?:AssertionError|TypeError|ReferenceError|Error)(?:\s*\[[A-Z_]+\])?:.*|error:\s+.+)$/);
    if (exception) return [exception[1]];
    const diagnostic = line.match(/([\w./\\-]+\.(?:py|[cm]?[jt]sx?))(?::\d+(?::\d+)?|\(\d+,\d+\))\s*:?\s*(?:-\s*)?(.*(?:error|[A-Z]\d{3}).*)/i);
    if (diagnostic) return [`${diagnostic[1].replaceAll("\\", "/")}: ${diagnostic[2].replace(/\s+/g, " ").trim()}`];
    return [];
  }))].sort();

  let suggestion;
  if (status === "incomplete") {
    suggestion = "テストの成功が確認できないか、skip/xfail/todoが残っています。テスト選定と実行条件を確認し、未完了の条件を成功とみなさないでください。";
  } else if (status === "start_error") {
    suggestion = "実行ファイルと依存環境を確認し、lock済み環境を復旧してください。コードの期待値を変更しないでください。";
  } else if (status === "timeout") {
    suggestion = "ログから停止した検査を特定し、所有するプロセス・接続先・待ち条件を調べてください。タイムアウト延長だけで解消扱いにしないでください。";
  } else if (task.layer === "postgres" || task.layer === "integration" || /could not connect to server|connection refused|password authentication failed|127\.0\.0\.1:5432|environment_unavailable/i.test(output)) {
    suggestion = "PostgreSQLへの接続に失敗しました。ローカルDBコンテナが起動しているか確認してください: pnpm db:up";
    docs = "docs/development.md#実postgresqlの結合テスト";
  } else if (/ENOTFOUND|EAI_AGAIN|PermissionError|EACCES|EPERM|certificate|SSL/i.test(output)) {
    suggestion = "環境・接続・権限の失敗です。chained exceptionを読み、sandboxの失敗と本質的な不具合を切り分けてください。必要な通常承認経路を使い、盲目的な権限バイパスで解決しないでください。";
  } else if (/\bDOM\d{3}\b/.test(output)) {
    suggestion = "Domain層のアーキテクチャ制約違反を検出しました。外部レイヤーへの依存やフレームワークimportを排除し、値オブジェクトやエンティティの不変条件を保護してください。";
    docs = ".agents/rules/domain.md";
  } else if (/\bAPP\d{3}\b/.test(output)) {
    suggestion = "Application層のアーキテクチャ制約違反を検出しました。UseCaseの入出力境界、認可・トランザクション管理、Infrastructureへの直接依存排除を確認してください。";
    docs = ".agents/rules/application.md";
  } else if (/Forbidden import|Circular import|CycleError/i.test(output)) {
    suggestion = "レイヤー間またはパッケージ間の禁止import・循環依存を検出しました。オニオンアーキテクチャの依存方向（外側から内側へ）に従い、依存性逆転（DIP）またはインターフェース抽出を適用してください。";
    docs = "docs/README.md";
  } else if (/\bF401\b/.test(output)) {
    suggestion = "F401の未使用importを削除してください。公開APIの再exportなど公開契約に従って整え、ファイル全体のlintを外さないでください。";
  } else if (/mypy|pyright|types/i.test(task.label)) {
    suggestion = "モデルの型と公開契約を照合し、呼び出し元のNoneや絞り込み漏れを局所的に修正してください。castやignoreで隠蔽する前に呼び出し経路を確認してください。";
  } else if (/lint|format|architecture|boundaries|imports/i.test(task.label)) {
    suggestion = "該当ファイル・違反コードと設計規約を読み、適切なレイヤーや依存方向へ配置・修正してください。禁止ルールを安易に緩和しないでください。";
  } else {
    suggestion = "失敗したテストの期待値を受入条件と照合し、最小の再現で実装を修正してください。仕様の根拠なくassertionやfixtureを弱めないでください。";
  }

  const identity = diagnostics.length
    ? createHash("sha256").update(JSON.stringify([task.label, status, diagnostics])).digest("hex")
    : null;
  return { identity, diagnostics, suggestion, docs, requirements: task.requirements ?? [] };
}
