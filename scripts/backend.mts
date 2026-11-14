// Pythonツールのキャッシュを実行場所によらずリポジトリ内へ集約する。
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const cache = (...parts: string[]): string => resolve(ROOT, ".cache", ...parts);

const result = spawnSync("uv", process.argv.slice(2), {
  stdio: "inherit",
  windowsHide: true,
  env: {
    ...process.env,
    UV_CACHE_DIR: process.env.UV_CACHE_DIR?.trim() || cache("uv"),
    PYTHONPYCACHEPREFIX: cache("python"),
    MYPY_CACHE_DIR: cache("mypy"),
    RUFF_CACHE_DIR: cache("ruff"),
  },
});

if (result.error) console.error(result.error.message);
process.exitCode = result.status ?? 1;
