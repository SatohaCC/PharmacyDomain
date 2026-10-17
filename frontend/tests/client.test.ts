import { ApiError, errorText } from "../src/shared/api/errors";
import { describe, expect, it } from "vitest";
import { safeReturnPath, readInvitation } from "../src/shared/navigation/paths";
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
    expect(safeReturnPath(p)).toBe("/admin");
  });
  it("招待復帰先を許可する", () => {
    expect(safeReturnPath("/invitations/accept")).toBe("/invitations/accept");
  });
  it("fragmentから秘密を読みURLから除去する", () => {
    history.replaceState(null, "", "/invitations/accept#secret=sample");
    expect(readInvitation()).toBe("sample");
    expect(location.hash).toBe("");
  });
});
