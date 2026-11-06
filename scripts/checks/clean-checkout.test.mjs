import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createCleanWorktree, isContained, resolveCommit, verificationUvCacheDirectory } from "./verify-clean-checkout.mjs";

test("offline clean checkout reuses the configured or default uv cache across its steps", () => {
  assert.equal(
    verificationUvCacheDirectory("/tmp/worktree", {
      offline: true,
      configuredCacheDirectory: "/home/test/.cache/uv",
      defaultCacheDirectory: "/unused/default",
    }),
    "/home/test/.cache/uv",
  );
  assert.equal(
    verificationUvCacheDirectory("/tmp/worktree", {
      offline: true,
      defaultCacheDirectory: "/home/test/.cache/uv",
    }),
    "/home/test/.cache/uv",
  );
  assert.equal(verificationUvCacheDirectory("/tmp/worktree"), join("/tmp/worktree", ".uv-cache"));
  assert.throws(
    () => verificationUvCacheDirectory("/tmp/worktree", { offline: true }),
    /requires an available uv cache/,
  );
});

function runNodeTest(root, path) {
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  return spawnSync(process.execPath, ["--test", path], { cwd: root, encoding: "utf8", env });
}

function createRepository() {
  const root = mkdtempSync(join(tmpdir(), "clean-checkout-git-"));
  const git = (...args) => execFileSync("git", args, { cwd: root, stdio: "pipe" });
  mkdirSync(root, { recursive: true });
  git("init", "--quiet");
  git("config", "user.name", "Quality Test");
  git("config", "user.email", "quality@example.invalid");
  writeFileSync(join(root, "tracked.txt"), "committed input\n");
  git("add", "tracked.txt");
  git("commit", "--quiet", "-m", "fixture");
  return { root, git };
}

test("clean worktree includes the requested commit and excludes local-only files", () => {
  const { root, git } = createRepository();
  const externalData = join(root, "local-only.data");
  writeFileSync(externalData, "not in the commit");
  let worktree;
  try {
    const revision = resolveCommit(root, "HEAD");
    worktree = createCleanWorktree(root, revision);
    assert.equal(worktree.revision, revision);
    assert.equal(readFileSync(join(worktree.path, "tracked.txt"), "utf8").replaceAll("\r\n", "\n"), "committed input\n");
    assert.equal(existsSync(join(worktree.path, "local-only.data")), false);
    assert.equal(isContained(worktree.tempRoot, worktree.path), true);
    assert.equal(isContained(worktree.tempRoot, root), false);
  } finally {
    worktree?.cleanup();
    assert.equal(git("worktree", "list", "--porcelain").toString().split("\nworktree ").length, 1);
    rmSync(root, { recursive: true, force: true });
  }
});

test("clean checkout rejects an untracked test input and accepts a tracked fixture", () => {
  const { root, git } = createRepository();
  const localTest = [
    'import assert from "node:assert/strict";',
    'import test from "node:test";',
    'import { readFileSync } from "node:fs";',
    'test("reads a local-only input", () => assert.equal(readFileSync(new URL("./local-only.data", import.meta.url), "utf8"), "local"));',
  ].join("\n");
  const fixtureTest = [
    'import assert from "node:assert/strict";',
    'import test from "node:test";',
    'import { readFileSync } from "node:fs";',
    'test("reads a tracked fixture", () => assert.equal(readFileSync(new URL("./fixture.data", import.meta.url), "utf8"), "fixture"));',
  ].join("\n");
  writeFileSync(join(root, "local-only.test.mjs"), localTest, "utf8");
  writeFileSync(join(root, "fixture.test.mjs"), fixtureTest, "utf8");
  writeFileSync(join(root, "fixture.data"), "fixture", "utf8");
  writeFileSync(join(root, "local-only.data"), "local", "utf8");
  git("add", "local-only.test.mjs", "fixture.test.mjs", "fixture.data");
  git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "--no-verify", "-m", "clean checkout inputs");

  let worktree;
  try {
    const localResult = runNodeTest(root, "local-only.test.mjs");
    const fixtureResult = runNodeTest(root, "fixture.test.mjs");
    assert.equal(localResult.status, 0, localResult.stderr);
    assert.equal(fixtureResult.status, 0, fixtureResult.stderr);

    worktree = createCleanWorktree(root, "HEAD");
    const isolatedLocalResult = runNodeTest(worktree.path, "local-only.test.mjs");
    const isolatedFixtureResult = runNodeTest(worktree.path, "fixture.test.mjs");
    assert.notEqual(isolatedLocalResult.status, 0, "untracked input must fail in clean worktree");
    assert.equal(isolatedFixtureResult.status, 0, isolatedFixtureResult.stderr);
  } finally {
    worktree?.cleanup();
    rmSync(root, { recursive: true, force: true });
  }
});
