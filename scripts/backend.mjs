// Pythonツールのキャッシュを実行場所によらずリポジトリ内へ集約する。
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const cache = (name) => fileURLToPath(new URL(`../.cache/${name}`, import.meta.url));
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
