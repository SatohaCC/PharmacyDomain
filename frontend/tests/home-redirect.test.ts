import { describe, expect, it } from "vitest";
import type {
  CurrentActorDto,
  SelectableStoreDto,
} from "../src/features/auth/api/actor-api";
import { resolveHomeRedirect } from "../src/features/auth/api/home-redirect";

function buildActor(overrides: Partial<CurrentActorDto> = {}): CurrentActorDto {
  return {
    person_id: "person-1",
    account_id: "account-1",
    membership_id: "membership-1",
    corporate_id: "corp-1",
    roles: ["member"],
    staff_id: "staff-1",
    store_ids: ["store-1"],
    managed_store_ids: [],
    permissions: [],
    selected_store_id: null,
    ...overrides,
  };
}

const sampleStores: SelectableStoreDto[] = [
  { id: "store-1", name: "シード薬局 本店", code: "SEED-001" },
];

describe("resolveHomeRedirect", () => {
  it("一般ユーザーに選択済み店舗がある場合は患者一覧へ遷移する", async () => {
    const target = await resolveHomeRedirect(
      async () => buildActor({ selected_store_id: "store-selected" }),
      async () => sampleStores,
    );
    expect(target).toEqual({
      to: "/stores/$storeId/patients",
      params: { storeId: "store-selected" },
    });
  });

  it("一般ユーザーに選択済み店舗がなくても所属店舗がある場合は先頭店舗の患者一覧へ遷移する", async () => {
    const target = await resolveHomeRedirect(
      async () => buildActor({ roles: ["member"], selected_store_id: null }),
      async () => sampleStores,
    );
    expect(target).toEqual({
      to: "/stores/$storeId/patients",
      params: { storeId: "store-1" },
    });
  });

  it("システム管理者は所属店舗があっても管理画面へ遷移する", async () => {
    const target = await resolveHomeRedirect(
      async () =>
        buildActor({
          roles: ["vendor_system_admin"],
          selected_store_id: null,
        }),
      async () => sampleStores,
    );
    expect(target).toEqual({ to: "/admin" });
  });

  it("店舗未所属の管理者は管理画面へ遷移する", async () => {
    const target = await resolveHomeRedirect(
      async () =>
        buildActor({
          roles: ["corporate_admin"],
          store_ids: [],
          selected_store_id: null,
        }),
      async () => [],
    );
    expect(target).toEqual({ to: "/admin" });
  });

  it("アクター取得に失敗した場合は管理画面へフォールバックする", async () => {
    const target = await resolveHomeRedirect(
      async () => {
        throw new Error("network error");
      },
      async () => sampleStores,
    );
    expect(target).toEqual({ to: "/admin" });
  });
});
