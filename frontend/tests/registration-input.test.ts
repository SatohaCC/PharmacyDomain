import { expect, it } from "vitest";
import { registrationInput } from "../src/features/users/model/registration-input";
it("登録入力はメールや期限を要求せずパスワードの空白を保持する", () => {
  const data = new FormData();
  data.set("login_id", " test-admin ");
  data.set("initial_password", "  test-password-12345  ");
  const input = registrationInput(data, "corporate_admin");
  expect(input.loginId).toBe("test-admin");
  expect(input.initialPassword).toBe("  test-password-12345  ");
});
it("店舗権限には対象店舗を必要とする", () => {
  expect(() => registrationInput(new FormData(), "store_viewer")).toThrow(
    "店舗を選択",
  );
});
it("複数店舗と入力の正規化を保持する", () => {
  const data = new FormData();
  data.set("last_name", " テスト ");
  data.append("store_ids", "store-1");
  data.append("store_ids", "store-2");
  const input = registrationInput(data, "store_operator");
  expect(input.names.last_name).toBe("テスト");
  expect(input.storeIds).toEqual(["store-1", "store-2"]);
});
