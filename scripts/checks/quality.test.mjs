import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, renameSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { buildQualityPlan, changedPaths, checkPostgresReachable, invocationFor, planFor, postgresConnectionTarget, requireSpecificationForScope, runPlan, scopesFor, taskResource } from "./quality.mjs";

test("レポート記録_失敗やタイムアウトや起動エラーおよび未実行タスクを区別して記録できる", () => {
  const folder = mkdtempSync(join(tmpdir(), "quality-report-"));
  try {
    const reportPath = join(folder, "report.json");
    const plan = ["success", "failure", "timeout", "missing"].map((label) => ({ label, command: process.execPath, args: [] }));
    const outcomes = [
      { status: 0 }, { status: 2 },
      { status: null, error: Object.assign(new Error("timeout"), { code: "ETIMEDOUT" }) },
      { status: null, error: Object.assign(new Error("missing"), { code: "ENOENT" }) },
    ];
    let index = 0;
    assert.equal(runPlan(plan, () => {
      const current = JSON.parse(readFileSync(reportPath, "utf8"));
      assert.equal(current.tasks[index].status, "not_run");
      assert.notEqual(current.status, "passed");
      return outcomes[index++];
    }, reportPath), 1);
    const report = JSON.parse(readFileSync(reportPath, "utf8"));
    assert.deepEqual(report.tasks.map((task) => task.status), ["passed", "failed", "timeout", "start_error"]);
    assert.equal(report.status, "failed");
    assert.equal(report.tasks[1].exitCode, 2);
    assert.deepEqual(report.excludedLayers, ["postgres", "browser"]);
    assert.equal(runPlan([], undefined, reportPath), 0);
    assert.equal(JSON.parse(readFileSync(reportPath, "utf8")).status, "not_run");
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("品質ランナー_環境変数で明示指定されたuvキャッシュパスを維持する", () => {
  const previousCacheDirectory = process.env.UV_CACHE_DIR;
  const configuredCacheDirectory = join(tmpdir(), "shared-uv-cache");
  let receivedCacheDirectory;
  process.env.UV_CACHE_DIR = configuredCacheDirectory;
  try {
    assert.equal(runPlan([{ label: "cache", command: "node", args: [] }], (_command, _args, options) => {
      receivedCacheDirectory = options.env.UV_CACHE_DIR;
      return { status: 0 };
    }), 0);
  } finally {
    if (previousCacheDirectory === undefined) delete process.env.UV_CACHE_DIR;
    else process.env.UV_CACHE_DIR = previousCacheDirectory;
  }
  assert.equal(receivedCacheDirectory, configuredCacheDirectory);
});

test("変更ファイル検知_リネーム両端を保持し共有設定変更時は全スコープを選択する", () => {
  const folder = mkdtempSync(join(tmpdir(), "quality-git-"));
  const git = (...args) => execFileSync("git", args, { cwd: folder, stdio: "pipe" });
  try {
    git("init");
    mkdirSync(join(folder, "backend"));
    writeFileSync(join(folder, "backend/old.py"), "fixture");
    writeFileSync(join(folder, "pnpm-lock.yaml"), "before");
    git("add", ".");
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--no-verify", "-m", "fixture");
    mkdirSync(join(folder, "scripts"));
    renameSync(join(folder, "backend/old.py"), join(folder, "scripts/new.py"));
    git("add", ".");
    writeFileSync(join(folder, "pnpm-lock.yaml"), "after");
    writeFileSync(join(folder, "backend/untracked.py"), "new");
    assert.deepEqual(changedPaths(folder), ["backend/old.py", "backend/untracked.py", "pnpm-lock.yaml", "scripts/new.py"]);
    assert.deepEqual(scopesFor(changedPaths(folder)), ["backend", "frontend", "scripts"]);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("スコープ判定_ドキュメントのみの変更時はランタイム検査を対象外とする", () => {
  assert.deepEqual(scopesFor(["docs/development.md", "AGENTS.md", "docs/README.md"]), []);
});

test("品質仕様要求_コード変更スコープには適用しドキュメント変更のみの場合は要求しない", () => {
  assert.equal(requireSpecificationForScope(true, ["frontend"]), true);
  assert.equal(requireSpecificationForScope(true, ["backend", "scripts"]), true);
  assert.equal(requireSpecificationForScope(true, []), false);
  assert.equal(requireSpecificationForScope(false, ["frontend"]), false);
});

test("スコープ判定_バックエンドおよび開発ツール変更から影響スコープを選択する", () => {
  assert.deepEqual(scopesFor(["backend/deleted.py"]), ["backend"]);
  assert.deepEqual(scopesFor(["backend/app/domain/model.py"]), ["backend"]);
  assert.deepEqual(scopesFor(["scripts/checks/quality.mjs"]), ["backend", "scripts"]);
  assert.deepEqual(scopesFor(["pnpm-lock.yaml"]), ["backend", "frontend", "scripts"]);
});

test("フル検査計画_DBやブラウザコマンドを含めずテスト・型・アーキテクチャ検査を計画する", () => {
  const plan = planFor(["backend", "frontend", "scripts"]);
  const commands = plan.map((task) => task.args.join(" ")).join("\n");
  assert.match(commands, /lint:backend/);
  assert.match(commands, /typecheck:backend/);
  assert.match(commands, /typecheck:frontend/);
  assert.match(commands, /test:backend -- -m not integration/);
  assert.match(commands, /backend\/tests\/tools\/hooks/);
  assert.doesNotMatch(commands, /test:integration|test:e2e/);
});

test("クイック検査計画_フルテストスイートを省略しバックエンドのMypyとRuffのみを計画する", () => {
  const labels = planFor(["backend", "frontend"], "quick").map((task) => task.label);
  assert.deepEqual(labels, ["Python lint", "Backend types", "Frontend lint"]);
  const mypy = planFor(["backend"], "quick").find((task) => task.label === "Backend types");
  assert.deepEqual(mypy.args, ["typecheck:backend"]);
});

test("コマンド実行生成_プラットフォーム差異を吸収しパッケージマネージャの引数を維持する", () => {
  const task = { command: "pnpm", args: ["test:backend", "-m", "not integration"] };
  const direct = invocationFor(task, "win32", "C:/Program Files/pnpm/pnpm.cjs");
  assert.equal(direct.shell, false);
  assert.equal(direct.args.at(-1), "not integration");
  const fallback = invocationFor(task, "win32", "");
  assert.equal(fallback.args.at(-1), '"not integration"');
});

test("計画実行_一部コマンドが失敗または未起動でもゲートを失敗とし残りの検査も実行する", () => {
  const plan = [{ label: "one", command: "node", args: [] }, { label: "two", command: "node", args: [] }];
  let calls = 0;
  assert.equal(runPlan(plan, () => ({ status: ++calls === 1 ? 1 : 0 })), 1);
  assert.equal(calls, 2);
  assert.equal(runPlan(plan, () => ({ status: null, error: new Error("missing executable") })), 1);
});

test("並列実行_concurrencyが1より大きい場合_タスクを並行実行する", async () => {
  const folder = mkdtempSync(join(tmpdir(), "quality-parallel-"));
  try {
    const reportPath = join(folder, "report.json");
    let active = 0;
    let maxActive = 0;
    const plan = [1, 2, 3, 4].map((n) => ({ label: `task-${n}`, command: "test", args: [] }));
    const mockExecute = async () => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((r) => setTimeout(r, 40));
      active--;
      return { status: 0, stdout: "ok\n" };
    };
    const exitCode = await runPlan(plan, mockExecute, reportPath, { concurrency: 2 });
    assert.equal(exitCode, 0);
    assert.ok(maxActive >= 2, `Expected concurrency >= 2, got ${maxActive}`);
    const report = JSON.parse(readFileSync(reportPath, "utf8"));
    assert.equal(report.status, "passed");
    assert.equal(report.tasks.length, 4);
    assert.equal(report.tasks.every((t) => t.status === "passed"), true);
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("レポート保存_存在しない親ディレクトリを初回のsave前に作成する", () => {
  const baseFolder = mkdtempSync(join(tmpdir(), "quality-nested-"));
  try {
    const reportPath = join(baseFolder, "deeply/nested/dir/report.json");
    const plan = [{ label: "save-test", command: "node", args: [] }];
    const exitCode = runPlan(plan, () => ({ status: 0 }), reportPath);
    assert.equal(exitCode, 0);
    const content = JSON.parse(readFileSync(reportPath, "utf8"));
    assert.equal(content.status, "passed");
  } finally {
    rmSync(baseFolder, { recursive: true, force: true });
  }
});

test("PostgreSQL疎通確認_ポートが閉じている場合でもハングせずに安全に失敗を検出する", async () => {
  const reachable = await checkPostgresReachable("127.0.0.1", 59999, 100);
  assert.equal(reachable, false);
});

test("PostgreSQL接続先_TEST_DATABASE_URLからホストとポートを正しく抽出する", () => {
  const targetWithPort = postgresConnectionTarget({
    TEST_DATABASE_URL: "postgresql+asyncpg://user:pass@127.0.0.1:5433/pharmacydomain",
  });
  assert.deepEqual(targetWithPort, { host: "127.0.0.1", port: 5433 });

  const targetDefaultPort = postgresConnectionTarget({
    TEST_DATABASE_URL: "postgresql+asyncpg://user:pass@dbhost/pharmacydomain",
  });
  assert.deepEqual(targetDefaultPort, { host: "dbhost", port: 5432 });

  const fallbackTarget = postgresConnectionTarget({
    POSTGRES_HOST: "my-postgres",
    POSTGRES_PORT: "5434",
  });
  assert.deepEqual(fallbackTarget, { host: "my-postgres", port: 5434 });
});

test("並列実行排他制御_同一DBリソースを使用するタスクの同時実行を防止する", async () => {
  const plan = [
    { label: "db-1", command: "test", args: ["db-1"], layer: "postgres" },
    { label: "db-2", command: "test", args: ["db-2"], layer: "integration" },
    { label: "non-db", command: "test", args: ["non-db"] },
  ];
  let activeDbTasks = 0;
  let maxActiveDbTasks = 0;
  const mockExecute = async (_cmd, args) => {
    const isDb = args[0]?.startsWith("db-");
    if (isDb) {
      activeDbTasks++;
      maxActiveDbTasks = Math.max(maxActiveDbTasks, activeDbTasks);
    }
    await new Promise((r) => setTimeout(r, 30));
    if (isDb) {
      activeDbTasks--;
    }
    return { status: 0, stdout: "ok\n" };
  };

  const exitCode = await runPlan(plan, mockExecute, null, { concurrency: 3 });
  assert.equal(exitCode, 0);
  assert.equal(maxActiveDbTasks, 1, `DB tasks must not run concurrently, got max ${maxActiveDbTasks}`);
});
