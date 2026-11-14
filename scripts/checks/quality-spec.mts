import { existsSync, readFileSync, realpathSync, statSync } from "node:fs";
import { resolve, sep } from "node:path";
import type { QualityTask, Specification } from "./types.mts";
import { processError } from "./types.mts";

export const DEFAULT_SPEC = "tmp/quality/task.json";

const SUITES: Record<string, { scope: string; command: string; args: string[]; testRunner: string }> = {
  postgres: {
    scope: "backend",
    command: "pnpm",
    args: ["test:integration"],
    testRunner: "pytest",
  },
  integration: {
    scope: "backend",
    command: "pnpm",
    args: ["test:integration"],
    testRunner: "pytest",
  },
  browser: {
    scope: "frontend",
    command: "pnpm",
    args: ["test:e2e"],
    testRunner: "playwright",
  },
};

export function registeredSuite(name: string) {
  return Object.hasOwn(SUITES, name) ? SUITES[name] : undefined;
}

function fields(value: unknown, names: string[]): asserts value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)
    || Object.keys(value).some((key) => !names.includes(key))) {
    throw new Error("Invalid quality specification fields");
  }
}

function text(value: unknown, name: string): asserts value is string {
  if (typeof value !== "string" || !value.trim() || value.length > 2000) {
    throw new Error(`Invalid ${name}`);
  }
}

export function specificationPlan(spec: unknown, root: string, phase = "full"): Specification {
  fields(spec, ["version", "task", "requirements"]);
  const specTask = spec.task;
  text(specTask, "task");
  if (spec.version !== 1 || !Array.isArray(spec.requirements) || !spec.requirements.length) {
    throw new Error("Specification requires version 1 and requirements");
  }
  const scopes = new Set<string>();
  const tasks = new Map<string, QualityTask>();
  const ids = new Set<string>();
  for (const requirement of spec.requirements) {
    fields(requirement, ["id", "acceptance", "checks"]);
    const requirementId = requirement.id;
    const acceptance = requirement.acceptance;
    text(requirementId, "requirement id");
    text(acceptance, "acceptance criterion");
    if (ids.has(requirementId) || !Array.isArray(requirement.checks) || !requirement.checks.length) {
      throw new Error("Requirements need unique ids and nonempty checks");
    }
    ids.add(requirementId);
    for (const check of requirement.checks) {
      fields(check, ["kind", "path", "test", "name"]);
      let command: string;
      let args: string[];
      let layer: string;
      let testRunner: string;
      let checkPath: string | undefined;
      let checkTest: string | undefined;
      let suiteName: string | undefined;
      if (check.kind === "suite") {
        suiteName = typeof check.name === "string" ? check.name : "";
        const suite = registeredSuite(suiteName);
        if (check.path !== undefined || check.test !== undefined || !suite) {
          throw new Error("Unknown integration suite");
        }
        layer = suiteName;
        scopes.add(suite.scope);
        if (phase === "quick") continue;
        ({ command, args, testRunner } = suite);
      } else {
        if (check.name !== undefined || typeof check.path !== "string"
          || !/^[a-zA-Z0-9_./-]+$/.test(check.path) || check.path.split("/").some((part) => !part || part === ".." || part === ".")) {
          throw new Error("Unsafe test path");
        }
        checkPath = check.path;
        const target = resolve(root, checkPath);
        if (!existsSync(target) || !statSync(target).isFile() || !realpathSync(target).startsWith(realpathSync(root) + sep)) {
          throw new Error("Test must be an existing file inside the repository");
        }
        const isPython = check.kind === "python" && /^backend\/tests\/.*test[^/]*\.py$/.test(checkPath);
        const isNode = check.kind === "node" && /^scripts\/.*\.test\.(?:mjs|mts)$/.test(checkPath);
        const isVitest = (check.kind === "vitest" || check.kind === "node") && /^frontend\/(tests|src)\/.*\.(?:test|spec)\.[jt]sx?$/.test(checkPath);
        if (!isPython && !isNode && !isVitest) {
          throw new Error("Unsupported test kind or location");
        }
        if (check.test !== undefined) {
          if (!isPython || typeof check.test !== "string" || !/^(?:test_|Test)[^\s:;"'`$\\|&<>(){}\[\]]+(?:::test_[^\s:;"'`$\\|&<>(){}\[\]]+)?$/u.test(check.test)) {
            throw new Error("Invalid pytest test selector");
          }
          checkTest = check.test;
        }
        scopes.add(checkPath.startsWith("backend/") ? "backend" : checkPath.startsWith("frontend/") ? "frontend" : "scripts");
        layer = "unit";
        if (isPython) {
          command = "uv";
          testRunner = "pytest";
          args = ["run", "--project", "backend", "--locked", "python", "-m", "pytest", checkPath + (checkTest ? `::${checkTest}` : ""), "-m", "not integration", "-q"];
        } else if (isVitest) {
          command = "pnpm";
          testRunner = "vitest";
          args = ["--filter", "pharmacydomain-admin", "test", "--", checkPath];
        } else {
          command = process.execPath;
          testRunner = "node";
          args = ["--test", "--test-timeout=60000", checkPath];
        }
      }
      const key = JSON.stringify([command, args]);
      let entry = tasks.get(key);
      if (!entry) {
        entry = {
          label: `Acceptance: ${checkPath ?? suiteName}${checkTest ? `::${checkTest}` : ""}`,
          command,
          args,
          layer,
          testRunner,
          requireEvidence: true,
          specification: specTask,
          requirements: [],
          reasons: [],
        };
        tasks.set(key, entry);
      }
      entry.requirements!.push(requirementId);
      entry.reasons!.push(acceptance);
    }
  }
  return { scopes: [...scopes].sort(), tasks: [...tasks.values()] };
}

export function loadSpecification(root: string, specPath?: string, phase = "full", required = false): Specification {
  const target = resolve(root, specPath ?? DEFAULT_SPEC);
  if (!existsSync(target) && specPath === undefined) {
    if (required) throw new Error("A quality specification is required for this operation. Create tmp/quality/task.json or pass --spec <path>.");
    return { scopes: [], tasks: [] };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(readFileSync(target, "utf8"));
  } catch (error) {
    throw new Error(`Invalid JSON in quality specification ${specPath ?? DEFAULT_SPEC}: ${processError(error).message}`, { cause: error });
  }
  return specificationPlan(parsed, root, phase);
}
