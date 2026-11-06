// Shared, read-only quality entry point for manual runs, CI and agent hooks.
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { createConnection } from "node:net";
import { resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { loadSpecification } from "./quality-spec.mjs";
import { acceptanceEvidence, failureFeedback } from "./quality-feedback.mjs";

export const ROOT = fileURLToPath(new URL("../../", import.meta.url));

export function scopesFor(paths) {
  const scopes = new Set();
  for (const path of paths) {
    if (/^(package\.json|pnpm-lock\.yaml|pnpm-workspace\.yaml|\.python-version|compose\.yaml|\.dockerignore|\.env.*)$/.test(path) || path.startsWith(".github/")) {
      for (const scope of ["backend", "frontend", "scripts"]) scopes.add(scope);
    }
    if (path.startsWith("backend/")) scopes.add("backend");
    if (path === "pytest.ini") {
      scopes.add("backend");
      scopes.add("scripts");
    }
    if (path.startsWith("frontend/")) scopes.add("frontend");
    if (path.startsWith("scripts/") || path.startsWith(".codex/") || path.startsWith(".agents/")) scopes.add("scripts");
    if (path.startsWith("scripts/checks/") || path.startsWith("scripts/hooks/")) scopes.add("backend");
  }
  return [...scopes].sort();
}

export function requireSpecificationForScope(required, scopes) {
  return Boolean(required && scopes.length > 0);
}

function nodeTests(folder, root = ROOT) {
  return readdirSync(resolve(root, folder), { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".test.mjs"))
    .map((entry) => relative(root, resolve(entry.parentPath, entry.name)).replaceAll("\\", "/"))
    .sort();
}

export function planFor(scopes, phase = "full") {
  const plan = [];
  const pnpm = (label, ...args) => plan.push({ label, command: "pnpm", args });
  const uv = (label, ...args) => plan.push({ label, command: "uv", args: ["run", "--project", "backend", "--locked", ...args] });
  const node = (label, args, options = {}) => plan.push({ label, command: process.execPath, args, ...options });

  if (scopes.includes("backend")) {
    if (phase === "quick") {
      uv("Python lint", "ruff", "check", "backend", "scripts/checks", "scripts/hooks");
      pnpm("Backend types", "typecheck:backend");
    } else {
      pnpm("Backend lint and architecture", "lint:backend");
      pnpm("Backend format", "format:check");
      pnpm("Backend types", "typecheck:backend");
      pnpm("Backend imports", "imports");
      pnpm("Backend tests", "test:backend");
    }
  }

  if (scopes.includes("frontend")) {
    pnpm("Frontend lint", "lint:frontend");
    if (phase === "full") {
      pnpm("Frontend types", "typecheck:frontend");
      pnpm("Frontend tests", "test:frontend");
      pnpm("Frontend build", "build");
    }
  }

  if (scopes.includes("scripts")) {
    if (phase === "full") {
      node("Development tooling tests", ["--test", "--test-timeout=60000", ...nodeTests("scripts")]);
    } else {
      node("Quality runner syntax", ["--check", "scripts/checks/quality.mjs"]);
    }
    uv("Tooling lint", "ruff", "check", "scripts/checks", "scripts/hooks");
    if (phase === "full") {
      uv("Tooling format", "ruff", "format", "--check", "scripts/checks", "scripts/hooks");
      pnpm("Tooling types (mypy)", "typecheck:scripts");
      uv("Hook regression tests", "python", "-m", "pytest", "scripts/hooks/test_quality_gate.py", "scripts/hooks/test_privacy_gate.py", "scripts/hooks/test_antigravity_adapter.py", "-q");
    }
  }

  return plan;
}

export function buildQualityPlan(scopes, specification, phase = "full") {
  const combinedScopes = [...new Set([...scopes, ...specification.scopes])];
  return [
    ...specification.tasks,
    ...planFor(combinedScopes, phase),
  ];
}

export function changedPaths(root = ROOT) {
  const collect = (args) => {
    const result = spawnSync("git", args, { cwd: root, encoding: "utf8" });
    if (result.status !== 0) throw new Error(result.stderr || "Cannot inspect Git changes");
    return result.stdout.split("\0").filter(Boolean);
  };
  return [...new Set([
    ...collect(["diff", "HEAD", "--name-only", "-z", "--no-renames"]),
    ...collect(["ls-files", "--others", "--exclude-standard", "-z"]),
  ])].sort();
}

export function executeAsync(command, args, options = {}) {
  return new Promise((resolve) => {
    let child;
    let stdout = "";
    let stderr = "";
    try {
      child = spawn(command, args, {
        cwd: options.cwd,
        shell: options.shell,
        env: options.env,
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (error) {
      resolve({ status: null, error, stdout: "", stderr: "" });
      return;
    }
    const maxBuffer = options.maxBuffer ?? 16 * 1024 * 1024;
    child.stdout?.setEncoding("utf8");
    child.stderr?.setEncoding("utf8");
    child.stdout?.on("data", (chunk) => {
      stdout += chunk;
      if (stdout.length + stderr.length > maxBuffer) {
        child.kill();
        resolve({ status: null, error: new Error("maxBuffer exceeded"), stdout, stderr });
      }
    });
    child.stderr?.on("data", (chunk) => {
      stderr += chunk;
      if (stdout.length + stderr.length > maxBuffer) {
        child.kill();
        resolve({ status: null, error: new Error("maxBuffer exceeded"), stdout, stderr });
      }
    });
    let timer;
    if (options.timeout) {
      timer = setTimeout(() => {
        const timeoutError = new Error("ETIMEDOUT");
        timeoutError.code = "ETIMEDOUT";
        child.kill();
        resolve({ status: null, error: timeoutError, stdout, stderr });
      }, options.timeout);
    }
    child.on("error", (error) => {
      if (timer) clearTimeout(timer);
      resolve({ status: null, error, stdout, stderr });
    });
    child.on("close", (status) => {
      if (timer) clearTimeout(timer);
      resolve({ status, error: null, stdout, stderr });
    });
  });
}

function recordTaskResult(report, index, task, result, started, save) {
  Object.assign(report.tasks[index], {
    status: result.error?.code === "ETIMEDOUT" ? "timeout"
      : result.error ? "start_error" : result.status === 0 ? "passed" : "failed",
    exitCode: result.status ?? null,
    durationMs: Date.now() - started,
  });
  const output = `${result.stdout ?? ""}\n${result.stderr ?? ""}`;
  if (task.requireEvidence && report.tasks[index].status === "passed") {
    const evidence = acceptanceEvidence(output, task.testRunner);
    report.tasks[index].evidence = evidence;
    if (!evidence.passed || evidence.incomplete) report.tasks[index].status = "incomplete";
  }
  const feedback = failureFeedback(task, report.tasks[index].status, output);
  report.tasks[index].feedback = feedback;

  console.log(`\n[quality] ${task.label}`);
  if (result.stdout) process.stdout.write(result.stdout);
  if (result.stderr) process.stderr.write(result.stderr);
  if (feedback) console.error(`[quality] Next: ${feedback.suggestion} See ${feedback.docs}`);
  if (report.tasks[index].status !== "passed") {
    console.error(`[quality] FAILED: ${task.label}${result.error ? `: ${result.error.message}` : ""}`);
  }

  report.status = report.tasks.some((entry) => entry.status === "not_run") ? "not_run"
    : report.tasks.every((entry) => entry.status === "passed") ? "passed" : "failed";
  save();

  return report.tasks[index].status !== "passed";
}

export function checkPostgresReachable(host = process.env.POSTGRES_HOST || "127.0.0.1", port = Number(process.env.POSTGRES_PORT || 5432), timeoutMs = 500) {
  return new Promise((resolve) => {
    const socket = createConnection({ host, port });
    let settled = false;
    const done = (ok) => {
      if (!settled) {
        settled = true;
        socket.destroy();
        resolve(ok);
      }
    };
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
  });
}

export function runPlan(plan, execute = spawnSync, reportPath = null, { concurrency = 1 } = {}) {
  let failed = false;
  const report = {
    version: 1,
    status: "not_run",
    excludedLayers: ["postgres", "browser"]
      .filter((layer) => !plan.some((task) => task.layer === layer)),
    tasks: plan.map((task) => ({ ...task, status: "not_run", exitCode: null, durationMs: 0 })),
  };
  const save = () => {
    if (reportPath) writeFileSync(reportPath, JSON.stringify(report, null, 2));
  };
  save();
  const temporary = resolve(ROOT, "tmp/quality");
  mkdirSync(temporary, { recursive: true });
  const execOptions = {
    cwd: ROOT,
    stdio: "pipe",
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
    timeout: 300_000,
    env: { ...process.env, UV_CACHE_DIR: process.env.UV_CACHE_DIR?.trim() || resolve(ROOT, ".uv-cache"), TMP: temporary, TEMP: temporary, TMPDIR: temporary },
  };

  if (concurrency > 1 || (execute && (execute === executeAsync || execute.constructor?.name === "AsyncFunction"))) {
    return (async () => {
      const completed = new Set();
      const inProgress = new Set();
      const waiters = new Set();

      function getNextTaskIndex() {
        for (let i = 0; i < plan.length; i++) {
          if (completed.has(i) || inProgress.has(i)) continue;
          inProgress.add(i);
          return i;
        }
        return -1;
      }

      function notifyWaiters() {
        for (const wake of waiters) wake();
        waiters.clear();
      }

      async function worker() {
        while (completed.size < plan.length) {
          const index = getNextTaskIndex();
          if (index === -1) {
            if (completed.size === plan.length) break;
            await new Promise((wake) => waiters.add(wake));
            continue;
          }
          const task = plan[index];
          let result;
          const started = Date.now();
          if ((task.layer === "postgres" || task.layer === "integration") && (execute === executeAsync || execute === spawnSync)) {
            const host = process.env.POSTGRES_HOST || "127.0.0.1";
            const port = Number(process.env.POSTGRES_PORT || 5432);
            const reachable = await checkPostgresReachable(host, port, 500);
            if (!reachable) {
              result = {
                status: 1,
                error: null,
                stdout: "",
                stderr: `PostgreSQL connection check failed: ${host}:${port} is not reachable.\nPlease start the database container with 'pnpm db:up'.`,
              };
            }
          }
          if (!result) {
            const invocation = invocationFor(task);
            result = await execute(invocation.command, invocation.args, {
              ...execOptions,
              shell: invocation.shell,
            });
          }
          if (recordTaskResult(report, index, task, result, started, save)) failed = true;
          inProgress.delete(index);
          completed.add(index);
          notifyWaiters();
        }
      }
      const workers = Array.from(
        { length: Math.min(concurrency, Math.max(1, plan.length)) },
        () => worker()
      );
      await Promise.all(workers);
      return Number(failed);
    })();
  }

  for (const [index, task] of plan.entries()) {
    const invocation = invocationFor(task);
    const started = Date.now();
    const result = execute(invocation.command, invocation.args, {
      ...execOptions,
      shell: invocation.shell,
    });
    if (recordTaskResult(report, index, task, result, started, save)) failed = true;
  }
  return Number(failed);
}

export function invocationFor(task, platform = process.platform, npmExecPath = process.env.npm_execpath) {
  if (task.command === "pnpm" && npmExecPath) {
    return /\.[cm]?js$/i.test(npmExecPath)
      ? { command: process.execPath, args: [npmExecPath, ...task.args], shell: false }
      : { command: npmExecPath, args: task.args, shell: false };
  }
  if (task.command === "pnpm" && platform === "win32") {
    if (task.args.some((value) => /["&|<>^%!\r\n]/.test(value))) throw new Error("Unsafe package command argument");
    return { command: "pnpm", args: task.args.map((value) => `"${value}"`), shell: true };
  }
  return { ...task, shell: false };
}

export async function main(args) {
  const phaseIndex = args.indexOf("--phase");
  const phase = phaseIndex < 0 ? "full" : args[phaseIndex + 1];
  const scopeIndex = args.indexOf("--scope");
  const scope = scopeIndex < 0 ? "all" : args[scopeIndex + 1];
  if (!["quick", "full"].includes(phase) || !["all", "backend", "frontend", "scripts"].includes(scope)) {
    throw new Error("Use --scope all|backend|frontend|scripts and --phase quick|full");
  }
  const scopes = args.includes("--changed") ? scopesFor(changedPaths())
    : scope === "all" ? ["backend", "frontend", "scripts"] : [scope];
  const specIndex = args.indexOf("--spec");
  if (specIndex >= 0 && (!args[specIndex + 1] || args[specIndex + 1].startsWith("--"))) {
    throw new Error("--spec requires a JSON path");
  }
  const specification = loadSpecification(
    ROOT,
    specIndex < 0 ? undefined : args[specIndex + 1],
    phase,
    requireSpecificationForScope(args.includes("--require-spec"), scopes),
  );
  const plan = buildQualityPlan(scopes, specification, phase);
  if (args.includes("--list")) {
    console.log(JSON.stringify(plan, null, 2));
    return 0;
  }
  if (!plan.length) console.log("[quality] No code or tooling changes to check.");
  const reportIndex = args.indexOf("--report");
  if (reportIndex >= 0 && !args[reportIndex + 1]) throw new Error("--report requires a path");

  const concurrencyIndex = args.indexOf("--concurrency");
  const concurrency = args.includes("--serial")
    ? 1
    : concurrencyIndex >= 0
      ? parseInt(args[concurrencyIndex + 1], 10)
      : (args.includes("--parallel") || phase === "full" ? 4 : 1);
  const executor = concurrency > 1 ? executeAsync : spawnSync;
  return await runPlan(plan, executor, reportIndex >= 0 ? resolve(args[reportIndex + 1]) : null, { concurrency });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
