import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const GUIDES = [
  "AGENTS.md",
  "scripts/README.md",
  "docs/development.md",
  "docs/README.md",
];
const TRACKED_PATHS = new Set([
  ...execFileSync("git", ["ls-files", "-z"], { cwd: ROOT, encoding: "utf8" }).split("\0").filter(Boolean),
  ...execFileSync("git", ["ls-files", "--others", "--exclude-standard", "-z"], { cwd: ROOT, encoding: "utf8" }).split("\0").filter(Boolean),
]);

function localMarkdownTargets(file: string) {
  const filePath = resolve(ROOT, file);
  if (!existsSync(filePath)) return [];
  const source = readFileSync(filePath, "utf8");
  return [...source.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)]
    .map((match) => match[1].trim().replace(/^<|>$/g, ""))
    .filter((target) => target && !target.startsWith("#") && !/^[a-z][a-z\d+.-]*:/i.test(target))
    .map((target) => ({
      source: file,
      target: target.split("#", 1)[0],
      absolute: resolve(ROOT, dirname(file), target.split("#", 1)[0]),
    }));
}

test("作業ガイド検証_作業用ガイド文書内のローカルリンク切れが存在しない", () => {
  const missing = GUIDES.flatMap(localMarkdownTargets)
    .filter(({ target, absolute }) => {
      if (!target) return false;
      const relativeTarget = relative(ROOT, absolute).replaceAll("\\", "/").replace(/\/$/, "");
      const tracked = relativeTarget === ""
        || TRACKED_PATHS.has(relativeTarget)
        || [...TRACKED_PATHS].some((path) => path.startsWith(`${relativeTarget}/`));
      return !existsSync(absolute) || !tracked;
    });

  assert.deepEqual(missing, []);
});
