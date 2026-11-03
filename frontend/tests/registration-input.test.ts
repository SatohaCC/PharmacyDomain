import { expect, it } from "vitest";
import { registrationInput } from "../src/features/users/model/registration-input";
it("メール未登録でもログインIDと店舗別ロールを取得する", () => {
  const data = new FormData();
  data.set("login_id", " staff-001 ");
  data.append("store_ids", "store-a");
  data.append("store_ids", "store-b");
  data.set("store_role_store-a", "store_operator");
  data.set("store_role_store-b", "store_viewer");
  data.set("home_store", "store-a");
  for (const id of data.getAll("store_ids"))
    data.set(`store_start_${id}`, "2026-11-01");
  const input = registrationInput(data, "member");
  expect(input.loginId).toBe("staff-001");
  expect(input.email).toBe("");
  expect(input.storeRoles).toEqual([
    { store_id: "store-a", role: "store_operator" },
    { store_id: "store-b", role: "store_viewer" },
  ]);
});
it("登録入力はメールを正規化しパスワードの空白を保持する", () => {
  const data = new FormData();
  data.set("email", " test-admin@example.test ");
  data.set("initial_password", "  test-password-12345  ");
  const input = registrationInput(data, "corporate_admin");
  expect(input.email).toBe("test-admin@example.test");
  expect(input.initialPassword).toBe("  test-password-12345  ");
});
it("店舗権限には対象店舗を必要とする", () => {
  expect(() => registrationInput(new FormData(), "member")).toThrow(
    "店舗を選択",
  );
});
it("複数店舗と入力の正規化を保持する", () => {
  const data = new FormData();
  data.set("last_name", " テスト ");
  data.append("store_ids", "store-1");
  data.append("store_ids", "store-2");
  data.set("home_store", "store-1");
  for (const id of data.getAll("store_ids"))
    data.set(`store_start_${id}`, "2026-10-01");
  const input = registrationInput(data, "member");
  expect(input.names.last_name).toBe("テスト");
  expect(input.storeIds).toEqual(["store-1", "store-2"]);
});

it("店舗ユーザーは主所属と開始日のない登録を拒否する", () => {
  const data = new FormData();
  data.append("store_ids", "store-1");
  expect(() => registrationInput(data, "member")).toThrow(
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

it("選択した店舗ごとの権限と週勤務時間をまとめて取得する", () => {
  const data = new FormData();
  data.append("store_ids", "store-a");
  data.append("store_ids", "store-b");
  data.set("home_store", "store-a");
  for (const id of data.getAll("store_ids"))
    data.set(`store_start_${id}`, "2026-11-03");
  data.set("store_role_store-a", "store_operator");
  data.set("store_role_store-b", "store_viewer");
  data.set("store_hours_store-a", "32");
  data.set("store_hours_store-b", "8.5");
  data.set("store_start_store-b", "2026-11-10");
  data.set("store_duty_store-a", "pharmacist");
  data.set("store_duty_store-b", "pharmacist");
  expect(registrationInput(data, "member").storeWorkConditions).toEqual([
    {
      store_id: "store-a",
      starts_on: "2026-11-03",
      weekly_hours: "32",
      duty: "pharmacist",
    },
    {
      store_id: "store-b",
      starts_on: "2026-11-10",
      weekly_hours: "8.5",
      duty: "pharmacist",
    },
  ]);
});

it.each(["-1", "168.01", "0.001", "NaN", "Infinity", "abc"])(
  "店舗別勤務時間が不正なら登録を止める: %s",
  (hours) => {
    const data = new FormData();
    data.append("store_ids", "store-a");
    data.set("home_store", "store-a");
    for (const id of data.getAll("store_ids"))
      data.set(`store_start_${id}`, "2026-11-03");
    data.set("store_hours_store-a", hours);
    expect(() => registrationInput(data, "member")).toThrow("週勤務時間");
  },
);

it("一店舗だけ所属開始日が未入力の場合は共通日付で補わず拒否する", () => {
  const data = new FormData();
  data.append("store_ids", "store-a");
  data.append("store_ids", "store-b");
  data.set("home_store", "store-a");
  data.set("store_start_store-a", "2026-11-03");
  expect(() => registrationInput(data, "member")).toThrow("各店舗の所属開始日");
});

it("店舗別合計が週所定労働時間を超える入力を拒否し未登録なら許可する", () => {
  const data = new FormData();
  data.append("store_ids", "a");
  data.append("store_ids", "b");
  data.set("home_store", "a");
  data.set("store_start_a", "2026-11-03");
  data.set("store_start_b", "2026-12-01");
  data.set("store_hours_a", "32");
  data.set("store_hours_b", "8.01");
  data.set("weekly_contract_hours", "40");
  expect(() => registrationInput(data, "member")).toThrow("合計");
  data.set("weekly_contract_hours", "");
  expect(registrationInput(data, "member").weeklyContractHours).toBeUndefined();
});
