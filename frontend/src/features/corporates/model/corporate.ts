export type CorporateType =
  | "stock_company"
  | "limited_liability_company"
  | "medical_corporation"
  | "general_incorporated_association"
  | "sole_proprietorship"
  | "other";

export const CORPORATE_TYPE_LABELS: Record<string, string> = {
  stock_company: "株式会社",
  limited_liability_company: "合同会社",
  medical_corporation: "医療法人",
  general_incorporated_association: "一般社団法人",
  sole_proprietorship: "個人事業主",
  other: "その他法人",
};

export const CORPORATE_TYPE_OPTIONS = Object.entries(
  CORPORATE_TYPE_LABELS,
).map(([value, label]) => ({ value, label }));

export interface Corporate {
  id: string;
  name: string;
  representative_name: string;
  is_active: boolean;
  corporate_type?: string;
  corporate_number?: string | null;
  invoice_number?: string | null;
  postal_code?: string | null;
  address_line?: string | null;
  phone_number?: string | null;
  email?: string | null;
}
export interface CorporateSearch {
  name?: string;
  status?: string;
  cursor?: string;
}
export interface CorporateList {
  items: Corporate[];
  next_cursor: string | null;
}
export interface CorporateInput {
  name: string;
  representative_last_name: string;
  representative_first_name: string;
  corporate_type?: string;
  corporate_number?: string | null;
  invoice_number?: string | null;
  postal_code?: string | null;
  address_line?: string | null;
  phone_number?: string | null;
  email?: string | null;
}
