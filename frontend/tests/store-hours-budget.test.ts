import { expect, it } from "vitest";
import { assessStoreHoursBudget } from "../src/features/users/model/store-hours-budget";
const change = (store: string, hours: string, starts = "2026-11-03") => ({
  store_id: store,
  starts_on: starts,
  effective_from: starts,
  weekly_hours: hours,
});
it("合計が上限と同じなら許可し小数の超過と将来の超過を検出する", () => {
  expect(
    assessStoreHoursBudget(
      40,
      [change("a", "32"), change("b", "8")],
      [],
      "2026-11-03",
    ).exceededOn,
  ).toBeNull();
  expect(
    assessStoreHoursBudget(
      40,
      [change("a", "32"), change("b", "8.01", "2026-12-01")],
      [],
      "2026-11-03",
    ).exceededOn,
  ).toBe("2026-12-01");
  expect(
    assessStoreHoursBudget(
      0.3,
      [change("a", "0.1"), change("b", "0.2")],
      [],
      "2026-11-03",
    ).exceededOn,
  ).toBeNull();
});
it("未設定の契約時間をゼロとして拒否しない", () => {
  expect(
    assessStoreHoursBudget(null, [change("a", "32")], [], "2026-11-03")
      .exceededOn,
  ).toBeNull();
});
