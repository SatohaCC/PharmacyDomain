import { assessStoreHoursBudget } from "./store-hours-budget";
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
  loginId: string;
  email: string;
  initialPassword: string;
  storeIds: string[];
  storeRoles: { store_id: string; role: string }[];
  storeWorkConditions: {
    store_id: string;
    starts_on: string;
    weekly_hours: string | null;
    duty: string;
  }[];
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
  const startDate = text(`store_start_${homeStore}`);
  if ((homeStore && !startDate) || (!homeStore && startDate))
    throw new Error("主所属店舗と所属開始日は両方指定してください。");
  if (role !== "corporate_admin" && (!homeStore || !startDate))
    throw new Error("店舗ユーザーには主所属店舗と所属開始日が必要です。");
  if (homeStore && storeIds.length && !storeIds.includes(homeStore))
    throw new Error("主所属店舗を利用権限に含めてください。");

  const storeWorkConditions = storeIds.map((id) => {
    const startsOn = text(`store_start_${id}`);
    if (!startsOn) throw new Error("各店舗の所属開始日を指定してください。");
    const hours = text(`store_hours_${id}`);
    if (hours && (!/^\d+(?:\.\d{1,2})?$/.test(hours) || Number(hours) > 168))
      throw new Error(
        "店舗ごとの週勤務時間は0～168、小数第2位までで入力してください。",
      );
    return {
      store_id: id,
      starts_on: startsOn,
      weekly_hours: hours || null,
      duty: text(`store_duty_${id}`) || "other",
    };
  });
  if (storeIds.length && (!homeStore || !startDate))
    throw new Error("所属店舗には主所属店舗と所属開始日が必要です。");
  const rawHours = text("weekly_contract_hours");
  let weeklyContractHours: number | undefined;
  if (rawHours !== "") {
    const parsed = Number(rawHours);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 80) {
      throw new Error("週所定労働時間は0以上80以下の数値で指定してください。");
    }
    weeklyContractHours = parsed;
  }

  const budget = assessStoreHoursBudget(
    weeklyContractHours,
    storeWorkConditions.map((item) => ({
      ...item,
      effective_from: item.starts_on,
    })),
    [],
    new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(
      new Date(),
    ),
  );
  if (budget.exceededOn)
    throw new Error(
      `店舗別の週勤務時間の合計（${budget.maximumHours}時間）が週所定労働時間（${weeklyContractHours}時間）を超えています。`,
    );
  return {
    names: {
      last_name: text("last_name"),
      first_name: text("first_name"),
      last_name_kana: text("last_name_kana"),
      first_name_kana: text("first_name_kana"),
    },
    homeStore,
    startDate,
    loginId: text("login_id"),
    email: text("email"),
    initialPassword: String(data.get("initial_password") || ""),
    storeIds,
    storeWorkConditions,
    storeRoles: storeIds.map((id) => ({
      store_id: id,
      role: text(`store_role_${id}`) || "store_operator",
    })),
    employmentType: text("employment_type") || "regular",
    weeklyContractHours,
    jobTitle: text("job_title") || undefined,
    code: text("code") || undefined,
    pharmacistLicenseNumber: text("pharmacist_license_number") || undefined,
    registeredSellerNumber: text("registered_seller_number") || undefined,
  };
}
