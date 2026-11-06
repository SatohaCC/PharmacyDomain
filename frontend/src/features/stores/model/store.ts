export const STORE_STATUS_LABELS: Record<string, string> = {
  active: "営業中",
  suspended: "休止中",
  closed: "閉局",
};

export type BusinessWeekday =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export const ORDERED_WEEKDAYS: BusinessWeekday[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

export const WEEKDAY_LABELS: Record<BusinessWeekday, string> = {
  monday: "月曜日",
  tuesday: "火曜日",
  wednesday: "水曜日",
  thursday: "木曜日",
  friday: "金曜日",
  saturday: "土曜日",
  sunday: "日曜日",
};

export interface BusinessHourSlot {
  opens_at: string;
  closes_at: string;
}

export interface WeekdayBusinessHours {
  weekday: BusinessWeekday | string;
  slots: BusinessHourSlot[];
}

export interface BusinessDayException {
  on: string;
  slots: BusinessHourSlot[];
  note?: string | null;
}

export interface BusinessHours {
  weekly: WeekdayBusinessHours[];
  exceptions: BusinessDayException[];
}

export interface Store {
  id: string;
  name: string;
  name_kana: string;
  code: string | null;
  status?: string;
  is_community_linkage?: boolean;
  is_specialized_linkage?: boolean;
  is_health_support?: boolean;
}
export interface StoreInput {
  name: string;
  name_kana: string;
  postal_code: string;
  address: string;
  phone_number: string;
  name_romaji: string | null;
  fax_number: string | null;
  email: string | null;
  code: string | null;
  insurance_pharmacy_number: string | null;
}

export interface StoreDetail {
  id: string;
  corporate_id: string;
  name: string;
  name_kana: string;
  name_romaji: string | null;
  postal_code: string;
  address: string;
  phone_number: string;
  fax_number: string | null;
  email: string | null;
  code: string | null;
  insurance_pharmacy_number: string | null;
  status: string;
  licenses?: unknown | null;
  safety_manager_id?: string | null;
  public_expense_designations?: {
    public_assistance_number?: string | null;
    support_for_independence_number?: string | null;
    intractable_disease_number?: string | null;
    workers_accident_number?: string | null;
  } | null;
  certifications?: {
    community_linkage?: {
      certification_number: string;
      valid_from: string;
      valid_to: string;
    } | null;
    specialized_linkage?: {
      certification_number: string;
      disease_category: string;
      valid_from: string;
      valid_to: string;
    } | null;
    health_support?: {
      notified_on: string;
    } | null;
  } | null;
  is_community_linkage?: boolean;
  is_specialized_linkage?: boolean;
  is_health_support?: boolean;
  business_hours?: BusinessHours | null;
}

export interface StoreNamesInput {
  name: string;
  name_kana: string;
  name_romaji?: string | null;
}

export interface StoreAddressInput {
  postal_code: string;
  address: string;
}

export interface StoreContactInput {
  phone_number: string;
  fax_number?: string | null;
  email?: string | null;
}

