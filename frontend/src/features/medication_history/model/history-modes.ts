export type DetailFooterMode =
  | "past_history"
  | "patient_timeline"
  | "usage_history"
  | "patient_summary"
  | "audit_alerts"
  | "questionnaire"
  | "remaining_medication"
  | "lab_tests";

export interface FooterFeatureDefinition {
  id: DetailFooterMode;
  label: string;
}

export const DETAIL_FOOTER_ITEMS: readonly FooterFeatureDefinition[] = [
  { id: "past_history", label: "過去処方・薬歴" },
  { id: "patient_timeline", label: "タイムライン" },
  { id: "usage_history", label: "使用薬剤履歴" },
  { id: "patient_summary", label: "患者サマリー" },
  { id: "audit_alerts", label: "処方監査" },
  { id: "questionnaire", label: "問診・入力" },
  { id: "remaining_medication", label: "残薬確認" },
  { id: "lab_tests", label: "検査値" },
];

export interface PrescriptionMedicineSummary {
  code: string | null;
  name: string;
  amount: string;
  unit: string;
}

export interface PrescriptionRpSummary {
  rp_number: number;
  category: string;
  quantity: number;
  dosage_name: string;
  medicines: PrescriptionMedicineSummary[];
}

export interface PrescriptionSummaryForHistory {
  id: string;
  document_number: string;
  issued_date: string;
  institution_name: string;
  rps: PrescriptionRpSummary[];
}

export interface DrugUsageSummaryItem {
  key: string;
  code: string;
  name: string;
  unit: string;
  totalQuantity: number;
  prescriptionCount: number;
  latestIssuedDate: string;
  latestDosageName: string;
}

/** 処方箋一覧から薬剤ごとの累積使用回数・処方日数と最新用法を集計する。 */
export function aggregateDrugUsage(
  prescriptions: readonly PrescriptionSummaryForHistory[],
): DrugUsageSummaryItem[] {
  const map = new Map<string, DrugUsageSummaryItem>();
  const sorted = [...prescriptions].sort((a, b) =>
    b.issued_date.localeCompare(a.issued_date),
  );

  for (const rx of sorted) {
    for (const rp of rx.rps) {
      for (const med of rp.medicines) {
        const key = `${med.code ?? ""}:${med.name}`;
        const existing = map.get(key);
        if (existing) {
          existing.totalQuantity += rp.quantity;
          existing.prescriptionCount += 1;
        } else {
          map.set(key, {
            key,
            code: med.code ?? "—",
            name: med.name,
            unit: med.unit,
            totalQuantity: rp.quantity,
            prescriptionCount: 1,
            latestIssuedDate: rx.issued_date,
            latestDosageName: rp.dosage_name,
          });
        }
      }
    }
  }
  return Array.from(map.values());
}

/** 保存されたフッターID順に従って機能一覧を並び替える。未知のIDは無視し、未指定の項目は末尾に残す。 */
export function orderFooterItems(
  items: readonly FooterFeatureDefinition[],
  orderIds: readonly string[],
): FooterFeatureDefinition[] {
  if (orderIds.length === 0) return [...items];
  const byId = new Map(items.map((item) => [item.id, item]));
  const result: FooterFeatureDefinition[] = [];
  for (const id of orderIds) {
    const matched = byId.get(id as DetailFooterMode);
    if (matched) {
      result.push(matched);
      byId.delete(id as DetailFooterMode);
    }
  }
  for (const remaining of byId.values()) {
    result.push(remaining);
  }
  return result;
}

const FOOTER_ORDER_KEY_PREFIX = "pharmacy_footer_order:";

export function loadStoreFooterOrder(storeId: string): string[] {
  try {
    const raw = window.localStorage.getItem(`${FOOTER_ORDER_KEY_PREFIX}${storeId}`);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((x): x is string => typeof x === "string")
      : [];
  } catch {
    return [];
  }
}

export function saveStoreFooterOrder(
  storeId: string,
  orderIds: readonly string[],
): void {
  try {
    window.localStorage.setItem(
      `${FOOTER_ORDER_KEY_PREFIX}${storeId}`,
      JSON.stringify(orderIds),
    );
  } catch {
    // ストレージ不可環境では無視する
  }
}
