/**
 * 薬歴ブロック（動的区分方式）のフロントエンドモデル定義。
 */

export type BlockSourceModule = string;

export interface MedicationHistoryBlock {
  id: string;
  category_code: string;
  category_name: string;
  category_badge_label: string;
  content: string;
  display_order: number;
  source_module: string;
  source_id?: string | null;
  updated_by?: string | null;
  updated_by_name: string;
  updated_at?: string | null;
}

export interface MedicationHistoryBlockInput {
  id?: string | null;
  category_code: string;
  content: string;
  display_order: number;
  source_module?: BlockSourceModule;
  source_id?: string | null;
}

export interface CategoryOption {
  code: string;
  name: string;
  badge_label: string;
  is_soap?: boolean;
}

export const DEFAULT_SOAP_CATEGORIES: CategoryOption[] = [
  { code: "s", name: "S（主観的情報）", badge_label: "S", is_soap: true },
  { code: "o", name: "O（客観的情報）", badge_label: "O", is_soap: true },
  { code: "a", name: "A（評価・判断）", badge_label: "A", is_soap: true },
  { code: "p", name: "P（計画）", badge_label: "P", is_soap: true },
];

export interface CurrentRecordHearingItem {
  field_id: string;
  label: string;
  value: string;
  category_code?: string;
}
