import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { invocationFor } from "./quality.mjs";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));

function runGit(root, args) {
  const result = spawnSync("git", args, {
    cwd: root,
    encoding: "utf8",
    windowsHide: true,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(result.stderr.trim() || `git ${args[0]} failed with exit code ${result.status}`);
  }
  return result.stdout.trim();
}

export function isContained(parent, target) {
  const child = relative(resolve(parent), resolve(target));
  return Boolean(child && child !== ".." && !child.startsWith(`..${sep}`) && !isAbsolute(child));
}

export function verificationUvCacheDirectory(worktreePath, {
  offline = false,
  configuredCacheDirectory,
  defaultCacheDirectory,
} = {}) {
  if (!offline) return join(worktreePath, ".uv-cache");
  const cacheDirectory = configuredCacheDirectory?.trim() || defaultCacheDirectory?.trim();
  if (!cacheDirectory) throw new Error("Offline clean-checkout verification requires an available uv cache");
  return cacheDirectory;
}

export function resolveCommit(root, ref) {
  if (typeof ref !== "string" || !ref.trim()) throw new Error("A Git commit or ref is required");
  let revision;
  try {
    revision = runGit(root, ["rev-parse", "--verify", "--end-of-options", String(ref) + "^{commit}"]);
  } catch (error) {
    throw new Error("Cannot resolve commit " + ref + ": " + (error instanceof Error ? error.message : String(error)), { cause: error });
  }
  if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(revision)) {
    throw new Error("Git returned an invalid commit identifier");
  }
  return revision;
}

export function createCleanWorktree(root, ref, tempParent = tmpdir()) {
  const repository = resolve(root);
  const revision = resolveCommit(repository, ref);
  const tempRoot = mkdtempSync(join(tempParent, "pharmacydomain-clean-checkout-"));
  const path = join(tempRoot, "worktree");
  if (!isContained(tempRoot, path)) {
    rmSync(tempRoot, { recursive: true, force: true });
    throw new Error("Verification worktree path escaped its owned temporary directory");
  }
  try {
    runGit(repository, ["worktree", "add", "--quiet", "--detach", path, revision]);
  } catch (error) {
    rmSync(tempRoot, { recursive: true, force: true });
    throw error;
  }

  let cleaned = false;
  return {
    path,
    revision,
    tempRoot,
    cleanup() {
      if (cleaned) return;
      if (!isContained(tempRoot, path)) {
        throw new Error("Refusing to remove a worktree outside its owned temporary directory");
      }
      runGit(repository, ["worktree", "remove", "--force", path]);
      if (existsSync(tempRoot)) rmSync(tempRoot, { recursive: true, force: true });
      cleaned = true;
    },
  };
}

function runStep(label, command, args, cwd, steps, { shell = false, env = process.env } = {}) {
  console.log(`[clean-checkout] ${label}`);
  const result = spawnSync(command, args, {
    cwd,
    stdio: "inherit",
    windowsHide: true,
    shell,
    env,
  });
  const status = result.status ?? 1;
  steps.push({
    label,
    status: result.error ? "start_error" : status === 0 ? "passed" : "failed",
    exitCode: result.status,
    ...(result.error ? { error: result.error.message } : {}),
  });
  if (result.error || status !== 0) {
    throw new Error(`${label} failed${result.error ? ` to start: ${result.error.message}` : ` with exit code ${status}`}`);
  }
}

function pnpmInvocation(args) {
  return invocationFor({ command: "pnpm", args }, process.platform, process.env.npm_execpath);
}

export function verifyCleanCheckout(ref, { offline = false } = {}) {
  const worktree = createCleanWorktree(ROOT, ref);
  const steps = [];
  const record = {
    version: 1,
    status: "failed",
    requestedRef: ref,
    commit: worktree.revision,
    steps,
  };
  let error = null;
  try {
    const configuredCachePath = process.env.UV_CACHE_DIR?.trim();
    const configuredCacheDirectory = configuredCachePath
      ? isAbsolute(configuredCachePath) ? configuredCachePath : resolve(ROOT, configuredCachePath)
      : undefined;
    let defaultCacheDirectory;
    if (offline && !configuredCacheDirectory) {
      const cacheEnvironment = { ...process.env };
      delete cacheEnvironment.UV_CACHE_DIR;
      const cacheResult = spawnSync("uv", ["cache", "dir"], {
        cwd: ROOT,
        encoding: "utf8",
        windowsHide: true,
        env: cacheEnvironment,
      });
      if (cacheResult.error || cacheResult.status !== 0 || !cacheResult.stdout.trim()) {
        throw new Error(`Cannot find the default uv cache${cacheResult.error ? `: ${cacheResult.error.message}` : ""}`);
      }
      defaultCacheDirectory = cacheResult.stdout.trim();
    }
    const pythonEnvironment = {
      ...process.env,
      UV_CACHE_DIR: verificationUvCacheDirectory(worktree.path, {
        offline,
        configuredCacheDirectory,
        defaultCacheDirectory,
      }),
    };
    const installArgs = ["install", "--frozen-lockfile", ...(offline ? ["--offline"] : [])];
    const pnpmInstall = pnpmInvocation(installArgs);
    runStep("Install locked Node dependencies", pnpmInstall.command, pnpmInstall.args, worktree.path, steps, {
      shell: pnpmInstall.shell,
    });
    runStep(
      "Install locked Python dependencies",
      "uv",
      ["sync", "--project", "backend", "--locked", ...(offline ? ["--offline"] : [])],
      worktree.path,
      steps,
      { env: pythonEnvironment },
    );

    const reportPath = "tmp/quality/clean-checkout.json";
    mkdirSync(join(worktree.path, "tmp/quality"), { recursive: true });
    const quality = pnpmInvocation(["quality", "--report", reportPath]);
    runStep("Run full quality suite", quality.command, quality.args, worktree.path, steps, {
      shell: quality.shell,
      env: pythonEnvironment,
    });
    const fullReportPath = join(worktree.path, reportPath);
    if (!existsSync(fullReportPath)) throw new Error("Full quality report was not written");
    record.quality = JSON.parse(readFileSync(fullReportPath, "utf8"));
    if (record.quality.status !== "passed") throw new Error(`Full quality report status is ${record.quality.status}`);
    record.status = "passed";
  } catch (caught) {
    error = caught instanceof Error ? caught.message : String(caught);
    record.error = error;
  } finally {
    try {
      worktree.cleanup();
    } catch (cleanupError) {
      console.error("[clean-checkout] Cleanup failed:", cleanupError);
    }
  }
  return record;
}

export function main(args = process.argv.slice(2)) {
  const refIndex = args.indexOf("--ref");
  const ref = refIndex >= 0 ? args[refIndex + 1] : undefined;
  if (!ref || ref.startsWith("--")) {
    console.error("Usage: node scripts/checks/verify-clean-checkout.mjs --ref <commit> [--offline]");
    return 1;
  }
  const offline = args.includes("--offline");
  const record = verifyCleanCheckout(ref, { offline });
  console.log(JSON.stringify(record, null, 2));
  return record.status === "passed" ? 0 : 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = main();
}
