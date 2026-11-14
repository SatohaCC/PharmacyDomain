import { describe, expect, it } from "vitest";
import {
  aggregateDrugUsage,
  buildThreeVisitComparison,
  buildTimelineEntries,
  DETAIL_FOOTER_ITEMS,
  filterByStoreId,
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

  it("直近3回比較で3件未満の記録を右詰めの3スロットに正規化し差分を判定する", () => {
    const prescriptions = {
      "rx-1": {
        id: "rx-1",
        document_number: "RX-001",
        issued_date: "2026-10-01",
        institution_name: "テストクリニック",
        rps: [
          {
            rp_number: 1,
            category: "internal",
            quantity: 14,
            dosage_name: "1日1回朝食後",
            medicines: [
              { code: "M1", name: "アムロジピン錠5mg", amount: "1", unit: "錠" },
              { code: "M2", name: "ジャヌビア錠50mg", amount: "1", unit: "錠" },
            ],
          },
        ],
      },
      "rx-2": {
        id: "rx-2",
        document_number: "RX-002",
        issued_date: "2026-11-01",
        institution_name: "テストクリニック",
        rps: [
          {
            rp_number: 1,
            category: "internal",
            quantity: 30,
            dosage_name: "1日1回朝食後",
            medicines: [
              { code: "M1", name: "アムロジピン錠5mg", amount: "2", unit: "錠" },
              { code: "M3", name: "メトホルミン錠250mg", amount: "1", unit: "錠" },
            ],
          },
        ],
      },
    };

    const result = buildThreeVisitComparison(
      [
        { id: "rec-1", prescription_id: "rx-1" },
        { id: "rec-2", prescription_id: "rx-2" },
      ],
      prescriptions,
    );

    expect(result.slots[0]).toBeNull();
    expect(result.slots[1]?.id).toBe("rec-1");
    expect(result.slots[2]?.id).toBe("rec-2");
    expect(result.summary).toEqual({
      addedCount: 1,
      changedCount: 1,
      discontinuedCount: 1,
      isDoPrescription: false,
      hasPrevious: true,
    });

    const rows = result.groups[0].rows;
    expect(rows[0].cells[2]).toMatchObject({
      status: "changed",
      doseChanged: true,
      quantityChanged: true,
    });
    expect(rows[1].cells[2]).toMatchObject({
      status: "discontinued",
      prevAmount: "1",
      prevQuantity: 14,
    });
    expect(rows[2].cells[2]).toMatchObject({
      status: "added",
      amount: "1",
      quantity: 30,
    });
  });

  it("前回と同一処方の場合はDo処方と判定する", () => {
    const rxBase = {
      document_number: "RX",
      issued_date: "2026-10-01",
      institution_name: "テストクリニック",
      rps: [
        {
          rp_number: 1,
          category: "internal",
          quantity: 14,
          dosage_name: "朝食後",
          medicines: [{ code: "M1", name: "薬A", amount: "1", unit: "錠" }],
        },
      ],
    };
    const result = buildThreeVisitComparison(
      [
        { id: "rec-1", prescription_id: "rx-1" },
        { id: "rec-2", prescription_id: "rx-2" },
      ],
      {
        "rx-1": { ...rxBase, id: "rx-1" },
        "rx-2": { ...rxBase, id: "rx-2" },
      },
    );
    expect(result.summary.isDoPrescription).toBe(true);
    expect(result.summary.addedCount).toBe(0);
    expect(result.summary.changedCount).toBe(0);
    expect(result.summary.discontinuedCount).toBe(0);
  });

  it("タイムライン統合で重複する来局イベントと薬歴を1件へ統合しソートする", () => {
    const records = [
      {
        id: "rec-1",
        event_id: "ev-1",
        event_type_name: "調剤",
        event_occurred_at: "2026-10-01T09:00:00Z",
        counseled_at: "2026-10-01T10:00:00Z",
        prescription_id: "rx-1",
      },
      {
        id: "rec-2",
        event_id: "ev-2",
        event_type_name: "調剤",
        event_occurred_at: "2026-11-01T09:00:00Z",
        counseled_at: "2026-11-01T10:00:00Z",
        prescription_id: "rx-2",
      },
    ];
    const events = [
      {
        event_id: "ev-1",
        event_type_name: "受付・調剤",
        occurred_at: "2026-10-01T09:00:00Z",
        prescription_id: "rx-1",
        medication_history_id: "rec-1",
      },
      {
        event_id: "ev-3",
        event_type_name: "フォロー電話",
        occurred_at: "2026-10-15T12:00:00Z",
        prescription_id: null,
        medication_history_id: null,
      },
    ];

    const desc = buildTimelineEntries(records, events, "desc");
    expect(desc.map((e) => e.occurredAt)).toEqual([
      "2026-11-01T10:00:00Z",
      "2026-10-15T12:00:00Z",
      "2026-10-01T10:00:00Z",
    ]);

    const asc = buildTimelineEntries(records, events, "asc");
    expect(asc.map((e) => e.occurredAt)).toEqual([
      "2026-10-01T10:00:00Z",
      "2026-10-15T12:00:00Z",
      "2026-11-01T10:00:00Z",
    ]);
  });

  it("勤務店舗を切り替えたとき対象店舗の薬歴・処方箋だけを残す", () => {
    const items = [
      { id: "rx-1", store_id: "store-a" },
      { id: "rx-2", store_id: "store-b" },
      { id: "rx-3", store_id: "store-a" },
    ];

    expect(filterByStoreId(items, "store-a").map((x) => x.id)).toEqual([
      "rx-1",
      "rx-3",
    ]);
    expect(filterByStoreId(items, "store-b").map((x) => x.id)).toEqual([
      "rx-2",
    ]);
    expect(filterByStoreId(items, "store-c")).toEqual([]);
  });
});
