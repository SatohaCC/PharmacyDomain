import type { UserRole } from "./registration";
export interface InvitationInput {
  names: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  };
  personId: string;
  staffId: string;
  homeStore: string;
  startDate: string;
  addressee: string;
  expiresAt: string;
  storeIds: string[];
}
export function invitationInput(
  data: FormData,
  role: UserRole,
  now: Date,
): InvitationInput {
  const text = (key: string) => String(data.get(key) || "").trim();
  const expires = new Date(text("expires_at"));
  if (!Number.isFinite(expires.valueOf()) || expires <= now)
    throw new Error("招待期限は未来日時を指定してください。");
  const storeIds = data.getAll("store_ids").map(String);
  if (role !== "corporate_admin" && !storeIds.length)
    throw new Error("許可する店舗を選択してください。");
  return {
    names: {
      last_name: text("last_name"),
      first_name: text("first_name"),
      last_name_kana: text("last_name_kana"),
      first_name_kana: text("first_name_kana"),
    },
    personId: text("person_id"),
    staffId: text("staff_id"),
    homeStore: text("home_store"),
    startDate: text("start_date"),
    addressee: text("addressee"),
    expiresAt: expires.toISOString(),
    storeIds,
  };
}
