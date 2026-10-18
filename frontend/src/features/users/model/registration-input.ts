import type { UserRole } from "./registration";
export interface RegistrationInput {
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
  loginId: string;
  initialPassword: string;
  storeIds: string[];
}
export function registrationInput(
  data: FormData,
  role: UserRole,
): RegistrationInput {
  const text = (key: string) => String(data.get(key) || "").trim();
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
    loginId: text("login_id"),
    initialPassword: String(data.get("initial_password") || ""),
    storeIds,
  };
}
