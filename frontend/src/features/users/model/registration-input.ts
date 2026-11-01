import type { UserRole } from "./registration";
export interface RegistrationInput {
  names: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  };
  homeStore: string;
  startDate: string;
  email: string;
  initialPassword: string;
  storeIds: string[];
  employmentType?: string;
  weeklyContractHours?: number;
  jobTitle?: string;
  code?: string;
  pharmacistLicenseNumber?: string;
  registeredSellerNumber?: string;
}
export function registrationInput(
  data: FormData,
  role: UserRole,
): RegistrationInput {
  const text = (key: string) => String(data.get(key) || "").trim();
  const storeIds = data.getAll("store_ids").map(String);
  if (role !== "corporate_admin" && !storeIds.length)
    throw new Error("許可する店舗を選択してください。");
  const homeStore = text("home_store");
  const startDate = text("start_date");
  if ((homeStore && !startDate) || (!homeStore && startDate))
    throw new Error("主所属店舗と所属開始日は両方指定してください。");
  if (role !== "corporate_admin" && (!homeStore || !startDate))
    throw new Error("店舗ユーザーには主所属店舗と所属開始日が必要です。");
  if (homeStore && storeIds.length && !storeIds.includes(homeStore))
    throw new Error("主所属店舗を利用権限に含めてください。");

  const rawHours = text("weekly_contract_hours");
  let weeklyContractHours: number | undefined;
  if (rawHours !== "") {
    const parsed = Number(rawHours);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 80) {
      throw new Error("週所定労働時間は0以上80以下の数値で指定してください。");
    }
    weeklyContractHours = parsed;
  }

  return {
    names: {
      last_name: text("last_name"),
      first_name: text("first_name"),
      last_name_kana: text("last_name_kana"),
      first_name_kana: text("first_name_kana"),
    },
    homeStore,
    startDate,
    email: text("email"),
    initialPassword: String(data.get("initial_password") || ""),
    storeIds,
    employmentType: text("employment_type") || "regular",
    weeklyContractHours,
    jobTitle: text("job_title") || undefined,
    code: text("code") || undefined,
    pharmacistLicenseNumber: text("pharmacist_license_number") || undefined,
    registeredSellerNumber: text("registered_seller_number") || undefined,
  };
}
