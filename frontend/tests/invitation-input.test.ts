import { expect, it } from "vitest";
import { invitationInput } from "../src/features/users/model/invitation-input";
const now = new Date("2026-10-18T00:00:00Z");
it.each(["invalid", "2026-10-18T00:00:00Z", "2026-10-17T00:00:00Z"])(
  "期限%sは未来日時として受け入れない",
  (expires) => {
    const data = new FormData();
    data.set("expires_at", expires);
    expect(() => invitationInput(data, "corporate_admin", now)).toThrow(
      "未来日時",
    );
  },
);
it("店舗権限には対象店舗を必要とする", () => {
  const data = new FormData();
  data.set("expires_at", "2030-01-01T00:00:00Z");
  expect(() => invitationInput(data, "store_viewer", now)).toThrow(
    "店舗を選択",
  );
});
it("複数店舗と入力の正規化を保持する", () => {
  const data = new FormData();
  data.set("expires_at", "2030-01-01T00:00:00Z");
  data.set("last_name", " テスト ");
  data.append("store_ids", "store-1");
  data.append("store_ids", "store-2");
  const input = invitationInput(data, "store_operator", now);
  expect(input.names.last_name).toBe("テスト");
  expect(input.storeIds).toEqual(["store-1", "store-2"]);
  expect(input.expiresAt).toBe("2030-01-01T00:00:00.000Z");
});
