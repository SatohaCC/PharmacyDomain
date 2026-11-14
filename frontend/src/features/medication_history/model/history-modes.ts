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

export type MedicineDiffStatus =
  | "added"
  | "changed"
  | "unchanged"
  | "discontinued"
  | "absent";

export interface ComparisonRecordInput {
  id: string;
  prescription_id: string | null;
}

export interface ComparisonSlotCell {
  status: MedicineDiffStatus;
  name: string | null;
  amount: string | null;
  unit: string | null;
  quantity: number | null;
  prevAmount: string | null;
  prevUnit: string | null;
  prevQuantity: number | null;
  doseChanged: boolean;
  quantityChanged: boolean;
}

export interface ComparisonMedicineRow {
  key: string;
  medicineName: string;
  cells: [ComparisonSlotCell, ComparisonSlotCell, ComparisonSlotCell];
}

export interface ComparisonDosageGroup {
  key: string;
  label: string;
  rows: ComparisonMedicineRow[];
}

export interface ThreeVisitComparisonSummary {
  addedCount: number;
  changedCount: number;
  discontinuedCount: number;
  isDoPrescription: boolean;
  hasPrevious: boolean;
}

export interface ThreeVisitComparisonResult<
  TRecord extends ComparisonRecordInput,
> {
  slots: [TRecord | null, TRecord | null, TRecord | null];
  groups: ComparisonDosageGroup[];
  summary: ThreeVisitComparisonSummary;
}

interface RawSlotMedicine {
  name: string;
  amount: string;
  unit: string;
  quantity: number;
}

function makeAbsentCell(): ComparisonSlotCell {
  return {
    status: "absent",
    name: null,
    amount: null,
    unit: null,
    quantity: null,
    prevAmount: null,
    prevUnit: null,
    prevQuantity: null,
    doseChanged: false,
    quantityChanged: false,
  };
}

/**
 * 古い順（最大3件）の記録を固定3列スロット `[2回前, 前回, 今回]` に正規化し、
 * 用法グループ・薬剤ごとの差分状態と前回からの変更サマリーを構築する。
 */
export function buildThreeVisitComparison<
  TRecord extends ComparisonRecordInput,
>(
  chronologicalRecords: readonly TRecord[],
  prescriptionsById: Readonly<Record<string, PrescriptionSummaryForHistory>>,
): ThreeVisitComparisonResult<TRecord> {
  const trimmed = chronologicalRecords.slice(-3);
  const slots: [TRecord | null, TRecord | null, TRecord | null] = [
    trimmed.length === 3 ? trimmed[0] : null,
    trimmed.length === 3 ? trimmed[1] : trimmed.length === 2 ? trimmed[0] : null,
    trimmed.length >= 1 ? trimmed[trimmed.length - 1] : null,
  ];

  const groupOrder: string[] = [];
  const groupMap = new Map<
    string,
    {
      label: string;
      rowOrder: string[];
      rows: Map<
        string,
        {
          medicineName: string;
          rawCells: [
            RawSlotMedicine | null,
            RawSlotMedicine | null,
            RawSlotMedicine | null,
          ];
        }
      >;
    }
  >();

  slots.forEach((record, colIdx) => {
    if (!record?.prescription_id) return;
    const rx = prescriptionsById[record.prescription_id];
    if (!rx) return;

    for (const rp of rx.rps) {
      const dosageKey = rp.dosage_name.trim() || `RP${rp.rp_number}`;
      const dosageLabel = rp.dosage_name.trim()
        ? `RP${rp.rp_number}: ${rp.dosage_name}`
        : `RP${rp.rp_number}`;

      let group = groupMap.get(dosageKey);
      if (!group) {
        group = {
          label: dosageLabel,
          rowOrder: [],
          rows: new Map(),
        };
        groupMap.set(dosageKey, group);
        groupOrder.push(dosageKey);
      }

      for (const med of rp.medicines) {
        const medKey = med.code ? `${med.code}:${med.name}` : med.name;
        let row = group.rows.get(medKey);
        if (!row) {
          row = {
            medicineName: med.name,
            rawCells: [null, null, null],
          };
          group.rows.set(medKey, row);
          group.rowOrder.push(medKey);
        }
        row.rawCells[colIdx] = {
          name: med.name,
          amount: med.amount,
          unit: med.unit,
          quantity: rp.quantity,
        };
      }
    }
  });

  let addedCount = 0;
  let changedCount = 0;
  let discontinuedCount = 0;

  const hasPrevious = Boolean(
    slots[1]?.prescription_id &&
      prescriptionsById[slots[1].prescription_id] &&
      slots[2]?.prescription_id &&
      prescriptionsById[slots[2].prescription_id],
  );

  const groups: ComparisonDosageGroup[] = groupOrder.map((gKey) => {
    const g = groupMap.get(gKey)!;
    const rows: ComparisonMedicineRow[] = g.rowOrder.map((rKey) => {
      const r = g.rows.get(rKey)!;
      const builtCells: [
        ComparisonSlotCell,
        ComparisonSlotCell,
        ComparisonSlotCell,
      ] = [makeAbsentCell(), makeAbsentCell(), makeAbsentCell()];

      for (let colIdx = 0; colIdx < 3; colIdx += 1) {
        const slotRecord = slots[colIdx];
        if (!slotRecord) {
          builtCells[colIdx] = makeAbsentCell();
          continue;
        }

        const curr = r.rawCells[colIdx];
        const prevRecordExists = colIdx > 0 && slots[colIdx - 1] !== null;
        const prev = prevRecordExists ? r.rawCells[colIdx - 1] : null;

        if (!prevRecordExists) {
          if (curr) {
            builtCells[colIdx] = {
              status: "unchanged",
              name: curr.name,
              amount: curr.amount,
              unit: curr.unit,
              quantity: curr.quantity,
              prevAmount: null,
              prevUnit: null,
              prevQuantity: null,
              doseChanged: false,
              quantityChanged: false,
            };
          } else {
            builtCells[colIdx] = makeAbsentCell();
          }
          continue;
        }

        if (!prev && curr) {
          builtCells[colIdx] = {
            status: "added",
            name: curr.name,
            amount: curr.amount,
            unit: curr.unit,
            quantity: curr.quantity,
            prevAmount: null,
            prevUnit: null,
            prevQuantity: null,
            doseChanged: false,
            quantityChanged: false,
          };
        } else if (prev && !curr) {
          builtCells[colIdx] = {
            status: "discontinued",
            name: prev.name,
            amount: null,
            unit: null,
            quantity: null,
            prevAmount: prev.amount,
            prevUnit: prev.unit,
            prevQuantity: prev.quantity,
            doseChanged: false,
            quantityChanged: false,
          };
        } else if (prev && curr) {
          const doseChanged =
            `${prev.amount}${prev.unit}` !== `${curr.amount}${curr.unit}`;
          const quantityChanged = prev.quantity !== curr.quantity;
          builtCells[colIdx] = {
            status: doseChanged || quantityChanged ? "changed" : "unchanged",
            name: curr.name,
            amount: curr.amount,
            unit: curr.unit,
            quantity: curr.quantity,
            prevAmount: prev.amount,
            prevUnit: prev.unit,
            prevQuantity: prev.quantity,
            doseChanged,
            quantityChanged,
          };
        } else {
          builtCells[colIdx] = makeAbsentCell();
        }
      }

      if (hasPrevious) {
        const latestCell = builtCells[2];
        if (latestCell.status === "added") addedCount += 1;
        if (latestCell.status === "changed") changedCount += 1;
        if (latestCell.status === "discontinued") discontinuedCount += 1;
      }

      return {
        key: rKey,
        medicineName: r.medicineName,
        cells: builtCells,
      };
    });

    return {
      key: gKey,
      label: g.label,
      rows,
    };
  });

  return {
    slots,
    groups,
    summary: {
      addedCount,
      changedCount,
      discontinuedCount,
      isDoPrescription:
        hasPrevious &&
        addedCount === 0 &&
        changedCount === 0 &&
        discontinuedCount === 0,
      hasPrevious,
    },
  };
}

export interface TimelineCareEventInput {
  event_id: string;
  event_type_name: string | null;
  occurred_at: string | null;
  prescription_id: string | null;
  medication_history_id: string | null;
}

export interface TimelineRecordInput {
  id: string;
  event_id: string;
  event_type_name: string | null;
  event_occurred_at: string | null;
  counseled_at: string | null;
  prescription_id: string | null;
}

export interface MergedTimelineEntry<TRecord extends TimelineRecordInput> {
  key: string;
  occurredAt: string | null;
  eventTypeName: string | null;
  prescriptionId: string | null;
  record: TRecord | null;
}

/** 薬歴と来局イベントを重複なく統合し、時系列順で返す。 */
export function buildTimelineEntries<TRecord extends TimelineRecordInput>(
  records: readonly TRecord[],
  careEvents: readonly TimelineCareEventInput[],
  order: "desc" | "asc" = "desc",
): Array<MergedTimelineEntry<TRecord>> {
  const recordById = new Map(records.map((r) => [r.id, r]));
  const recordByEventId = new Map(records.map((r) => [r.event_id, r]));
  const matchedRecordIds = new Set<string>();
  const entries: Array<MergedTimelineEntry<TRecord>> = [];

  for (const ev of careEvents) {
    const matched =
      (ev.medication_history_id
        ? recordById.get(ev.medication_history_id)
        : undefined) ?? recordByEventId.get(ev.event_id);
    if (matched) {
      matchedRecordIds.add(matched.id);
    }
    entries.push({
      key: `ev-${ev.event_id}`,
      occurredAt:
        matched?.counseled_at ??
        ev.occurred_at ??
        matched?.event_occurred_at ??
        null,
      eventTypeName: ev.event_type_name ?? matched?.event_type_name ?? null,
      prescriptionId: matched?.prescription_id ?? ev.prescription_id ?? null,
      record: matched ?? null,
    });
  }

  for (const rec of records) {
    if (matchedRecordIds.has(rec.id)) continue;
    entries.push({
      key: `rec-${rec.id}`,
      occurredAt: rec.counseled_at ?? rec.event_occurred_at ?? null,
      eventTypeName: rec.event_type_name ?? null,
      prescriptionId: rec.prescription_id ?? null,
      record: rec,
    });
  }

  entries.sort((a, b) => {
    const da = a.occurredAt ?? "";
    const db = b.occurredAt ?? "";
    return order === "desc" ? db.localeCompare(da) : da.localeCompare(db);
  });

  return entries;
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

/** 表示店舗で受け付けたレコード・処方箋だけに絞り込む。 */
export function filterByStoreId<T extends { store_id: string }>(
  items: readonly T[],
  storeId: string,
): T[] {
  return items.filter((item) => item.store_id === storeId);
}
