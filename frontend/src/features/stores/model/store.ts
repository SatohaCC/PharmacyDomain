export const STORE_STATUS_LABELS: Record<string, string> = {
  active: "営業中",
  suspended: "休止中",
  closed: "閉局",
};

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
