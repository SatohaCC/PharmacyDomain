import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const compiler = resolve(ROOT, "frontend/node_modules/typescript/bin/tsc");
const config = resolve(ROOT, "scripts/tsconfig.json");

test("スクリプト型検査_移行したランタイムおよびテストファイルをすべて対象に含む", () => {
  const result = spawnSync(process.execPath, [compiler, "--project", config, "--listFilesOnly"], {
    encoding: "utf8",
    timeout: 15000,
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  for (const file of [
    "types.mts",
    "quality.mts",
    "quality-spec.mts",
    "quality-feedback.mts",
    "verify-clean-checkout.mts",
    "quality.test.mts",
    "quality-spec.test.mts",
    "clean-checkout.test.mts",
    "docs-reference.test.mts",
    "tooling-types.test.mts",
  ]) {
    assert.ok(result.stdout.replaceAll("\\", "/").includes(`/scripts/checks/${file}`), file);
  }
  assert.ok(result.stdout.replaceAll("\\", "/").includes("/scripts/backend.mts"), "backend.mts");
});

test("スクリプト型検査_Checkスクリプトの型不整合と暗黙のanyを拒否する", () => {
  const qualityTmpRoot = resolve(ROOT, "tmp/quality");
  mkdirSync(qualityTmpRoot, { recursive: true });
  const root = mkdtempSync(join(qualityTmpRoot, "typecheck-"));
  try {
    writeFileSync(join(root, "tsconfig.json"), JSON.stringify({ extends: config, include: ["probe.mts"] }));
    writeFileSync(join(root, "probe.mts"), "const count: number = 'invalid'; export function identity(value) { return value; }");
    const result = spawnSync(process.execPath, [compiler, "--project", join(root, "tsconfig.json"), "--pretty", "false"], {
      encoding: "utf8",
      timeout: 15000,
    });
    assert.ok(result.status !== null && result.status > 0, result.stderr || result.stdout);
    assert.match(result.stdout, /TS2322/);
    assert.match(result.stdout, /TS7006/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
