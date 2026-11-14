import { ApiError, errorText } from "../src/shared/api/errors";
import { describe, expect, it } from "vitest";
import { safeReturnPath } from "../src/shared/navigation/paths";
describe("API境界", () => {
  it.each([
    [401, "再ログイン"],
    [403, "権限"],
    [404, "見つかりません"],
    [409, "競合"],
    [422, "入力"],
    [500, "サーバー"],
  ])("状態%sを案内する", (status, text) => {
    expect(errorText(new ApiError(status, ""))).toContain(text);
  });
  it("公開された日本語メッセージを保持する", () => {
    expect(errorText(new ApiError(422, "名前が必要です。"))).toContain(
      "名前が必要です。",
    );
  });
  it.each([
    "https://evil.test",
    "//evil.test",
    "/\\evil.test",
    "/auth/callback",
    "/login",
  ])("危険な戻り先を採用しない: %s", (p) => {
    expect(
      safeReturnPath(p, {
        fallbackPath: "/admin",
        allowedPrefixes: ["/admin", "/stores"],
      }),
    ).toBe("/admin");
  });
  it.each([
    "/",
    "/admin",
    "/admin/corporates",
    "/stores/01930000-0000-7000-8000-000000000006/patients",
  ])("安全な内部パスを許可する: %s", (p) => {
    expect(
      safeReturnPath(p, {
        fallbackPath: "/admin",
        allowedPrefixes: ["/admin", "/stores"],
      }),
    ).toBe(p);
  });
});
