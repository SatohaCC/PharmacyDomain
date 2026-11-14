import { describe, expect, it } from "vitest";
import {
  aggregateDrugUsage,
  DETAIL_FOOTER_ITEMS,
  orderFooterItems,
} from "../src/features/medication_history/model/history-modes";

describe("history-modes", () => {
  it("保存された順序でフッター機能一覧を並び替え、未指定項目は末尾に残す", () => {
    const ordered = orderFooterItems(DETAIL_FOOTER_ITEMS, [
      "audit_alerts",
      "patient_timeline",
      "unknown_mode",
    ]);
    expect(ordered[0].id).toBe("audit_alerts");
    expect(ordered[1].id).toBe("patient_timeline");
    expect(ordered).toHaveLength(DETAIL_FOOTER_ITEMS.length);
  });
  it("フッター機能定義にyakureki相当の8モードが揃っている", () => {
    expect(DETAIL_FOOTER_ITEMS.map((i) => i.id)).toEqual([
      "past_history",
      "patient_timeline",
      "usage_history",
      "patient_summary",
      "audit_alerts",
      "questionnaire",
      "remaining_medication",
      "lab_tests",
    ]);
  });

  it("複数の処方箋から薬剤ごとの累計日数と最新用法を集計する", () => {
    const result = aggregateDrugUsage([
      {
        id: "rx-1",
        document_number: "RX-001",
        issued_date: "2026-10-01",
        institution_name: "Aクリニック",
        rps: [
          {
            rp_number: 1,
            category: "internal",
            quantity: 14,
            dosage_name: "1日1回朝食後",
            medicines: [
              {
                code: "2171022F1020",
                name: "アムロジピン錠5mg",
                amount: "1",
                unit: "錠",
              },
            ],
          },
        ],
      },
      {
        id: "rx-2",
        document_number: "RX-002",
        issued_date: "2026-11-01",
        institution_name: "Aクリニック",
        rps: [
          {
            rp_number: 1,
            category: "internal",
            quantity: 28,
            dosage_name: "1日1回夕食後",
            medicines: [
              {
                code: "2171022F1020",
                name: "アムロジピン錠5mg",
                amount: "1",
                unit: "錠",
              },
            ],
          },
        ],
      },
    ]);

    expect(result).toEqual([
      {
        key: "2171022F1020:アムロジピン錠5mg",
        code: "2171022F1020",
        name: "アムロジピン錠5mg",
        unit: "錠",
        totalQuantity: 42,
        prescriptionCount: 2,
        latestIssuedDate: "2026-11-01",
        latestDosageName: "1日1回夕食後",
      },
    ]);
  });
});
