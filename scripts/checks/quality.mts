// Shared, read-only quality entry point for manual runs, CI and agent hooks.
import type { ChildProcess } from "node:child_process";
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createConnection } from "node:net";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { acceptanceEvidence, failureFeedback } from "./quality-feedback.mts";
import { loadSpecification } from "./quality-spec.mts";
import type {
  ExecutionResult,
  Executor,
  ProcessOptions,
  QualityReport,
  QualityTask,
  Specification,
} from "./types.mts";
import { processError } from "./types.mts";

export const ROOT = fileURLToPath(new URL("../../", import.meta.url));

export function scopesFor(paths: string[]): string[] {
  const scopes = new Set<string>();
  for (const path of paths) {
    if (/^(package\.json|pnpm-lock\.yaml|pnpm-workspace\.yaml|\.python-version|compose\.yaml|\.dockerignore|\.env.*)$/.test(path) || path.startsWith(".github/")) {
      for (const scope of ["backend", "frontend", "scripts"]) scopes.add(scope);
    }
    if (path.startsWith("backend/")) scopes.add("backend");
    if (path.startsWith("frontend/")) scopes.add("frontend");
    if (path.startsWith("scripts/") || path.startsWith(".codex/") || path.startsWith(".agents/")) scopes.add("scripts");
    if (path.startsWith("scripts/checks/")) scopes.add("backend");
  }
  return [...scopes].sort();
}

export function requireSpecificationForScope(required: boolean, scopes: string[]): boolean {
  return Boolean(required && scopes.length > 0);
}

function nodeTests(folder: string, root = ROOT): string[] {
  return readdirSync(resolve(root, folder), { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile() && /\.test\.(?:mjs|mts)$/.test(entry.name))
    .map((entry) => relative(root, resolve(entry.parentPath, entry.name)).replaceAll("\\", "/"))
    .sort();
}

export function planFor(scopes: string[], phase = "full"): QualityTask[] {
  const plan: QualityTask[] = [];
  const pnpm = (label: string, ...args: string[]) => plan.push({ label, command: "pnpm", args });
  const uv = (label: string, ...args: string[]) => plan.push({ label, command: "uv", args: ["run", "--project", "backend", "--locked", ...args] });
  const node = (label: string, args: string[], options: Partial<QualityTask> = {}) => plan.push({ label, command: process.execPath, args, ...options });

  if (scopes.includes("backend")) {
    if (phase === "quick") {
      uv("Python lint", "ruff", "check", "backend");
      pnpm("Backend types", "typecheck:backend");
    } else {
      pnpm("Backend lint and architecture", "lint:backend");
      pnpm("Backend format", "format:check");
      pnpm("Backend types", "typecheck:backend");
      pnpm("Backend imports", "imports");
      pnpm("Backend tests", "test:backend", "--", "-m", "not integration");
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
    pnpm("Tooling TypeScript types", "typecheck:tooling");
    if (phase === "full") {
      node("Development tooling tests", ["--test", "--test-timeout=60000", ...nodeTests("scripts")]);
    } else {
      node("Quality runner syntax", ["--check", "scripts/checks/quality.mts"]);
    }
    uv("Tooling lint", "ruff", "check", "backend/tools");
    if (phase === "full") {
      uv("Tooling format", "ruff", "format", "--check", "backend/tools");
      pnpm("Tooling types (mypy)", "typecheck:scripts");
      uv("Hook regression tests", "python", "-m", "pytest", "backend/tests/tools/hooks", "-q");
    }
  }

  return plan;
}

export function buildQualityPlan(scopes: string[], specification: Specification, phase = "full"): QualityTask[] {
  const combinedScopes = [...new Set([...scopes, ...specification.scopes])];
  return [
    ...specification.tasks,
    ...planFor(combinedScopes, phase),
  ];
}

export function changedPaths(root = ROOT): string[] {
  const collect = (args: string[]) => {
    const result = spawnSync("git", args, { cwd: root, encoding: "utf8" });
    if (result.status !== 0) throw new Error(result.stderr || "Cannot inspect Git changes");
    return result.stdout.split("\0").filter(Boolean);
  };
  return [...new Set([
    ...collect(["diff", "HEAD", "--name-only", "-z", "--no-renames"]),
    ...collect(["ls-files", "--others", "--exclude-standard", "-z"]),
  ])].sort();
}

export function executeAsync(command: string, args: string[], options: ProcessOptions = {}): Promise<ExecutionResult> {
  return new Promise((resolveResult) => {
    let child: ChildProcess;
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
      resolveResult({ status: null, error: processError(error), stdout: "", stderr: "" });
      return;
    }
    const maxBuffer = options.maxBuffer ?? 16 * 1024 * 1024;
    child.stdout?.setEncoding("utf8");
    child.stderr?.setEncoding("utf8");
    child.stdout?.on("data", (chunk: string | Buffer) => {
      stdout += String(chunk);
      if (stdout.length + stderr.length > maxBuffer) {
        child.kill();
        resolveResult({ status: null, error: new Error("maxBuffer exceeded"), stdout, stderr });
      }
    });
    child.stderr?.on("data", (chunk: string | Buffer) => {
      stderr += String(chunk);
      if (stdout.length + stderr.length > maxBuffer) {
        child.kill();
        resolveResult({ status: null, error: new Error("maxBuffer exceeded"), stdout, stderr });
      }
    });
    let timer: ReturnType<typeof setTimeout> | undefined;
    if (options.timeout) {
      timer = setTimeout(() => {
        const timeoutError: NodeJS.ErrnoException = new Error("ETIMEDOUT");
        timeoutError.code = "ETIMEDOUT";
        child.kill();
        resolveResult({ status: null, error: timeoutError, stdout, stderr });
      }, options.timeout);
    }
    child.on("error", (error) => {
      if (timer) clearTimeout(timer);
      resolveResult({ status: null, error, stdout, stderr });
    });
    child.on("close", (status) => {
      if (timer) clearTimeout(timer);
      resolveResult({ status, error: null, stdout, stderr });
    });
  });
}

function recordTaskResult(
  report: QualityReport,
  index: number,
  task: QualityTask,
  result: ExecutionResult,
  started: number,
  save: () => void,
): boolean {
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

export function postgresConnectionTarget(env: NodeJS.ProcessEnv = process.env): { host: string; port: number } {
  const urlString = env.TEST_DATABASE_URL;
  if (urlString) {
    try {
      const normalized = urlString.replace(/^[a-zA-Z0-9+_.-]+:\/\//, "http://");
      const parsed = new URL(normalized);
      const host = parsed.hostname || "127.0.0.1";
      const port = parsed.port ? Number(parsed.port) : 5432;
      return { host, port };
    } catch {
      // fallback to environment variables
    }
  }
  const host = env.POSTGRES_HOST || "127.0.0.1";
  const port = Number(env.POSTGRES_PORT || 5432);
  return { host, port };
}

export function checkPostgresReachable(
  hostOrTarget: string | { host?: string; port?: number } = postgresConnectionTarget(),
  portOrTimeout = 5432,
  maybeTimeout = 500,
): Promise<boolean> {
  let host = "127.0.0.1";
  let port = 5432;
  let timeoutMs = 500;
  if (typeof hostOrTarget === "object" && hostOrTarget !== null) {
    host = hostOrTarget.host || "127.0.0.1";
    port = Number(hostOrTarget.port || 5432);
    timeoutMs = typeof portOrTimeout === "number" ? portOrTimeout : 500;
  } else {
    host = hostOrTarget || "127.0.0.1";
    port = Number(portOrTimeout || 5432);
    timeoutMs = typeof maybeTimeout === "number" ? maybeTimeout : 500;
  }
  return new Promise((resolveReachable) => {
    const socket = createConnection({ host, port });
    let settled = false;
    const done = (ok: boolean) => {
      if (!settled) {
        settled = true;
        socket.destroy();
        resolveReachable(ok);
      }
    };
    socket.setTimeout(timeoutMs);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
  });
}

export function taskResource(task: Pick<QualityTask, "resource" | "layer">): string | null {
  if (task.resource) return task.resource;
  if (task.layer === "postgres" || task.layer === "integration") return "postgres-db";
  return null;
}

export function runPlan(
  plan: QualityTask[],
  execute: Executor = spawnSync as Executor,
  reportPath: string | null = null,
  { concurrency = 1 }: { concurrency?: number } = {},
): number | Promise<number> {
  let failed = false;
  const report: QualityReport = {
    version: 1,
    status: "not_run",
    excludedLayers: ["postgres", "browser"]
      .filter((layer) => !plan.some((task) => task.layer === layer)),
    tasks: plan.map((task) => ({ ...task, status: "not_run", exitCode: null, durationMs: 0 })),
  };
  const save = () => {
    if (reportPath) {
      mkdirSync(dirname(reportPath), { recursive: true });
      writeFileSync(reportPath, JSON.stringify(report, null, 2));
    }
  };
  save();
  const temporary = resolve(ROOT, "tmp/quality");
  mkdirSync(temporary, { recursive: true });
  const execOptions: ProcessOptions = {
    cwd: ROOT,
    stdio: "pipe",
    encoding: "utf8",
    maxBuffer: 16 * 1024 * 1024,
    timeout: 300_000,
    env: {
      ...process.env,
      UV_CACHE_DIR: process.env.UV_CACHE_DIR?.trim() || resolve(ROOT, ".cache/uv"),
      PYTHONPYCACHEPREFIX: resolve(ROOT, ".cache/python"),
      MYPY_CACHE_DIR: resolve(ROOT, ".cache/mypy"),
      RUFF_CACHE_DIR: resolve(ROOT, ".cache/ruff"),
      TMP: temporary,
      TEMP: temporary,
      TMPDIR: temporary,
    },
  };

  if (concurrency > 1 || (execute && (execute === executeAsync || execute.constructor?.name === "AsyncFunction"))) {
    return (async () => {
      const completed = new Set<number>();
      const inProgress = new Set<number>();
      const activeResources = new Set<string>();
      const waiters = new Set<() => void>();

      function getNextTaskIndex(): number {
        for (let i = 0; i < plan.length; i++) {
          if (completed.has(i) || inProgress.has(i)) continue;
          const resource = taskResource(plan[i]);
          if (resource && activeResources.has(resource)) continue;
          inProgress.add(i);
          if (resource) activeResources.add(resource);
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
            await new Promise<void>((wake) => waiters.add(wake));
            continue;
          }
          const task = plan[index];
          let result: ExecutionResult | undefined;
          const started = Date.now();
          try {
            if ((task.layer === "postgres" || task.layer === "integration") && (execute === executeAsync || execute === spawnSync)) {
              const { host, port } = postgresConnectionTarget();
              const reachable = await checkPostgresReachable({ host, port }, 500);
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
          } finally {
            inProgress.delete(index);
            const resource = taskResource(task);
            if (resource) activeResources.delete(resource);
            completed.add(index);
            notifyWaiters();
          }
        }
      }
      const workers = Array.from(
        { length: Math.min(concurrency, Math.max(1, plan.length)) },
        () => worker(),
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
    }) as ExecutionResult;
    if (recordTaskResult(report, index, task, result, started, save)) failed = true;
  }
  return Number(failed);
}

export function invocationFor(
  task: Pick<QualityTask, "command" | "args">,
  platform = process.platform,
  npmExecPath = process.env.npm_execpath,
): { command: string; args: string[]; shell: boolean } {
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

export async function main(args: string[]): Promise<number> {
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
  const executor: Executor = concurrency > 1 ? executeAsync : (spawnSync as Executor);
  return await runPlan(plan, executor, reportIndex >= 0 ? resolve(args[reportIndex + 1]) : null, { concurrency });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (error) {
    console.error(processError(error).message);
    process.exitCode = 1;
  }
}
