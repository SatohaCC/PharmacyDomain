import { expect, it } from "vitest";
import { registrationInput } from "../src/features/users/model/registration-input";
it("登録入力はメールを正規化しパスワードの空白を保持する", () => {
  const data = new FormData();
  data.set("email", " test-admin@example.test ");
  data.set("initial_password", "  test-password-12345  ");
  const input = registrationInput(data, "corporate_admin");
  expect(input.email).toBe("test-admin@example.test");
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
  data.set("home_store", "store-1");
  data.set("start_date", "2026-10-01");
  const input = registrationInput(data, "store_operator");
  expect(input.names.last_name).toBe("テスト");
  expect(input.storeIds).toEqual(["store-1", "store-2"]);
});

it("店舗ユーザーは主所属と開始日のない登録を拒否する", () => {
  const data = new FormData();
  data.append("store_ids", "store-1");
  expect(() => registrationInput(data, "store_operator")).toThrow(
    "主所属店舗と所属開始日",
  );
});

it("雇用形態・週所定労働時間（0時間ヘルプ含む）・資格・役職を正しく受け取る", () => {
  const data = new FormData();
  data.set("email", "staff@example.com");
  data.set("initial_password", "pass12345678901");
  data.set("employment_type", "part_time");
  data.set("weekly_contract_hours", "0.0");
  data.set("job_title", " パート薬剤師 ");
  data.set("code", "STF-999");
  data.set("pharmacist_license_number", "123456");

  const input = registrationInput(data, "corporate_admin");
  expect(input.employmentType).toBe("part_time");
  expect(input.weeklyContractHours).toBe(0.0);
  expect(input.jobTitle).toBe("パート薬剤師");
  expect(input.code).toBe("STF-999");
  expect(input.pharmacistLicenseNumber).toBe("123456");
});

it("週所定労働時間が不正な値の場合はエラーを送出する", () => {
  const data = new FormData();
  data.set("weekly_contract_hours", "-5");
  expect(() => registrationInput(data, "corporate_admin")).toThrow(
    "週所定労働時間",
  );

  data.set("weekly_contract_hours", "85");
  expect(() => registrationInput(data, "corporate_admin")).toThrow(
    "週所定労働時間",
  );
});
