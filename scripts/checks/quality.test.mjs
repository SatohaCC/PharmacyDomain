import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, renameSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { buildQualityPlan, changedPaths, checkPostgresReachable, invocationFor, planFor, requireSpecificationForScope, runPlan, scopesFor } from "./quality.mjs";

test("reports distinguish failure, timeout, launch error and unexecuted work", () => {
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

test("quality runner preserves an explicitly selected uv cache", () => {
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

test("real Git changes retain both sides of renames and shared settings select all scopes", () => {
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

test("documentation changes do not start runtime checks", () => {
  assert.deepEqual(scopesFor(["docs/development.md", "AGENTS.md", "docs/README.md"]), []);
});

test("required acceptance specifications apply to code scopes but not documentation-only changes", () => {
  assert.equal(requireSpecificationForScope(true, ["frontend"]), true);
  assert.equal(requireSpecificationForScope(true, ["backend", "scripts"]), true);
  assert.equal(requireSpecificationForScope(true, []), false);
  assert.equal(requireSpecificationForScope(false, ["frontend"]), false);
});

test("staged/deleted/backend and shared configuration select affected scopes", () => {
  assert.deepEqual(scopesFor(["backend/deleted.py"]), ["backend"]);
  assert.deepEqual(scopesFor(["pytest.ini"]), ["backend", "scripts"]);
  assert.deepEqual(scopesFor(["scripts/checks/quality.mjs"]), ["backend", "scripts"]);
  assert.deepEqual(scopesFor(["pnpm-lock.yaml"]), ["backend", "frontend", "scripts"]);
});

test("full checks include tests, types and architecture without DB/browser commands", () => {
  const plan = planFor(["backend", "frontend", "scripts"]);
  const commands = plan.map((task) => task.args.join(" ")).join("\n");
  assert.match(commands, /lint:backend/);
  assert.match(commands, /typecheck:backend/);
  assert.match(commands, /typecheck:frontend/);
  assert.match(commands, /test:backend/);
  assert.match(commands, /test_quality_gate.py/);
  assert.doesNotMatch(commands, /test:integration|test:e2e/);
});

test("quick checks include cached Backend Mypy and Ruff lint but omit full test suites", () => {
  const labels = planFor(["backend", "frontend"], "quick").map((task) => task.label);
  assert.deepEqual(labels, ["Python lint", "Backend types", "Frontend lint"]);
  const mypy = planFor(["backend"], "quick").find((task) => task.label === "Backend types");
  assert.deepEqual(mypy.args, ["typecheck:backend"]);
});

test("package manager forwarding preserves arguments across platforms", () => {
  const task = { command: "pnpm", args: ["test:backend", "-m", "not integration"] };
  const direct = invocationFor(task, "win32", "C:/Program Files/pnpm/pnpm.cjs");
  assert.equal(direct.shell, false);
  assert.equal(direct.args.at(-1), "not integration");
  const fallback = invocationFor(task, "win32", "");
  assert.equal(fallback.args.at(-1), '"not integration"');
});

test("failed or unstarted commands fail the gate and remaining checks still run", () => {
  const plan = [{ label: "one", command: "node", args: [] }, { label: "two", command: "node", args: [] }];
  let calls = 0;
  assert.equal(runPlan(plan, () => ({ status: ++calls === 1 ? 1 : 0 })), 1);
  assert.equal(calls, 2);
  assert.equal(runPlan(plan, () => ({ status: null, error: new Error("missing executable") })), 1);
});

test("runPlan executes tasks concurrently with concurrency > 1", async () => {
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

test("checkPostgresReachable detects closed ports gracefully without hanging", async () => {
  const reachable = await checkPostgresReachable("127.0.0.1", 59999, 100);
  assert.equal(reachable, false);
});

