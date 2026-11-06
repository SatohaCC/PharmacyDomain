import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { specificationPlan, loadSpecification } from "./quality-spec.mjs";
import { acceptanceEvidence, failureFeedback } from "./quality-feedback.mjs";
import { runPlan } from "./quality.mjs";

function fixture(run) {
  const root = mkdtempSync(join(tmpdir(), "quality-spec-"));
  mkdirSync(join(root, "backend/tests"), { recursive: true });
  writeFileSync(join(root, "backend/tests/test_contract.py"), "# fixture");
  const check = { kind: "python", path: "backend/tests/test_contract.py", test: "test_contract" };
  const spec = { version: 1, task: "contract", requirements: [{ id: "R1", acceptance: "reject unauthorized access", checks: [check] }] };
  try { run(root, spec, check); } finally { rmSync(root, { recursive: true, force: true }); }
}

test("acceptance criteria select tests even without matching changed paths and preserve reasons", () => fixture((root, spec) => {
  spec.requirements.push({ ...spec.requirements[0], id: "R2", acceptance: "fail closed" });
  const plan = specificationPlan(spec, root);
  assert.deepEqual(plan.scopes, ["backend"]);
  assert.equal(plan.tasks.length, 1);
  assert.deepEqual(plan.tasks[0].requirements, ["R1", "R2"]);
  assert.deepEqual(plan.tasks[0].reasons, ["reject unauthorized access", "fail closed"]);
  assert.ok(plan.tasks[0].args.includes("backend/tests/test_contract.py::test_contract"));
}));

test("missing requirements, unknown commands, unsafe paths and nonexistent tests fail closed", () => fixture((root, spec, check) => {
  for (const mutation of [
    () => ({ ...spec, requirements: [] }),
    () => ({ ...spec, command: "anything" }),
    () => ({ ...spec, requirements: [{ ...spec.requirements[0], checks: [] }] }),
    ...["../outside.py", "/backend/tests/test_contract.py", "backend/tests/../tests/test_contract.py", "backend/tests/missing.py", "backend/tests/test_contract.py;echo"].map((path) => () => ({ ...spec, requirements: [{ ...spec.requirements[0], checks: [{ ...check, path }] }] })),
  ]) assert.throws(() => specificationPlan(mutation(), root));
  assert.throws(() => loadSpecification(root, "missing.json"));
  assert.deepEqual(loadSpecification(root), { scopes: [], tasks: [] });
  assert.throws(() => loadSpecification(root, undefined, "full", true), /quality specification is required/);
}));

test("integration layers require an explicit specification and use only registered commands", () => fixture((root, spec) => {
  spec.requirements[0].checks = [
    { kind: "suite", name: "postgres" },
    { kind: "suite", name: "browser" },
  ];
  const plan = specificationPlan(spec, root);
  assert.deepEqual(plan.tasks.map((task) => task.args), [
    ["test:integration"],
    ["test:e2e"],
  ]);
  assert.deepEqual(plan.tasks.map((task) => task.testRunner), ["pytest", "playwright"]);
  assert.deepEqual(plan.scopes, ["backend", "frontend"]);
  assert.deepEqual(specificationPlan(spec, root, "quick").tasks, []);
  spec.requirements[0].checks = [{ kind: "suite", name: "shell" }];
  assert.throws(() => specificationPlan(spec, root));
}));

test("feedback retains stable failure identity across line shifts and distinguishes different failing tests", () => {
  const task = { label: "Acceptance contract", requirements: ["R1"] };
  const a = failureFeedback(task, "failed", "FAILED backend/tests/test_contract.py::test_access - AssertionError\n1 failed in 1.2s");
  const b = failureFeedback(task, "failed", "FAILED backend/tests/test_contract.py::test_access - AssertionError\n\n1 failed in 2.5s");
  const c = failureFeedback(task, "failed", "FAILED backend/tests/test_contract.py::test_other - AssertionError\n1 failed in 1.2s");
  assert.ok(a.identity);
  assert.equal(a.identity, b.identity);
  assert.notEqual(a.identity, c.identity);
  assert.deepEqual(a.requirements, ["R1"]);
});

test("feedback provides domain, application and postgres specific guidance", () => {
  const domainTask = { label: "Tooling architecture", requirements: ["D1"] };
  const domFeedback = failureFeedback(domainTask, "failed", "backend/app/domain/service.py:10: DOM001 Domain internal package is forbidden");
  assert.equal(domFeedback.docs, ".agents/rules/domain.md");
  assert.match(domFeedback.suggestion, /Domain層/);

  const appTask = { label: "Tooling architecture", requirements: ["A1"] };
  const appFeedback = failureFeedback(appTask, "failed", "backend/app/application/usecase.py:20: APP001 UseCase violation");
  assert.equal(appFeedback.docs, ".agents/rules/application.md");
  assert.match(appFeedback.suggestion, /Application層/);

  const dbTask = { label: "Acceptance: postgres", layer: "postgres", requirements: ["P1"] };
  const dbFeedback = failureFeedback(dbTask, "failed", "could not connect to server: Connection refused (0x0000274D/10061)");
  assert.equal(dbFeedback.docs, "docs/development.md#実postgresqlの結合テスト");
  assert.match(dbFeedback.suggestion, /pnpm db:up/);
});
