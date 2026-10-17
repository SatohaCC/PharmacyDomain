import { execFileSync } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { format } from "prettier";
const backend = fileURLToPath(new URL("../../backend/", import.meta.url));
const output = execFileSync(
  "uv",
  [
    "run",
    "python",
    "-c",
    "import json; from app.bootstrap import create_app; print(json.dumps(create_app().openapi()))",
  ],
  { cwd: backend, encoding: "utf8", env: { ...process.env, PYTHONUTF8: "1" } },
);
const schema = JSON.parse(output);
const dest = new URL("../src/shared/api/schema.d.ts", import.meta.url);
mkdirSync(new URL("../src/shared/api/", import.meta.url), { recursive: true });
writeFileSync(
  dest,
  await format(astToString(await openapiTS(schema)), { parser: "typescript" }),
);
