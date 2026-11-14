import { useState } from "react";
import { Panel } from "../../../../shared/ui/Panel";
import { Badge } from "../../../../shared/ui/Badge";
import {
  ContrastMatrixFrame,
  ContrastMatrixRow,
  ContrastHeaderCell,
  ContrastSectionBar,
  ContrastCell,
  ContrastDiffText,
  ContrastStatusTag,
  ContrastSummaryBanner,
  ContrastEmptySlotHeader,
  ContrastEmptySlotCell,
} from "../../../../shared/component/ContrastMatrix";
import {
  TimelineList,
  TimelineItem,
} from "../../../../shared/component/Timeline";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../../shared/ui/Table";
import {
  Title,
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  MetaText,
  Cards,
} from "../../../../shared/ui/Elements";
import { Button } from "../../../../shared/ui/Button";
import { Link } from "../../../../shared/ui/Link";
import { Alert, EmptyState } from "../../../../shared/ui/Alert";
import type { MedicationHistoryDto } from "../../api/record-api";
import {
  aggregateDrugUsage,
  buildThreeVisitComparison,
  buildTimelineEntries,
  type DetailFooterMode,
  type PrescriptionSummaryForHistory,
} from "../../model/history-modes";

export interface CareEventTimelineItem {
  event_id: string;
  event_type_name: string | null;
  occurred_at: string | null;
  prescription_id: string | null;
  medication_history_id: string | null;
}

export interface InteractionAuditSummary {
  prescriptionId: string;
  documentNumber: string;
  totalCombinations: number;
  contraindicatedCount: number;
  precautionCount: number;
  pairs: Array<{
    first_name: string;
    second_name: string;
    severity: string;
    description: string;
  }>;
}

export interface PatientSummaryStats {
  patientName: string;
  birthDate: string | null;
  allergiesCount: number;
  sideEffectsCount: number;
  medicalHistoriesCount: number;
  concomitantMedsCount: number;
}

export interface CenterWorkspacePanelProps {
  activeMode: DetailFooterMode;
  records: MedicationHistoryDto[];
  prescriptionsById: Record<string, PrescriptionSummaryForHistory>;
  careEvents: CareEventTimelineItem[];
  selectedRecordId: string | null;
  onSelectRecord: (recordId: string) => void;
  newEntryHref: string;
  patientSummary: PatientSummaryStats;
  auditReport: InteractionAuditSummary | null;
  auditLoading?: boolean;
  auditError?: string | null;
  onRunAudit?: (prescriptionId: string) => void;
}

const STATUS_LABELS: Record<string, string> = {
  draft: "下書き",
  finalized: "確定済み",
  amended: "修正済み",
};

function formatDate(iso: string | null): string {
  if (!iso) return "日時未設定";
  return iso.slice(0, 10);
}

function formatSlotStepLabel(visitsAgo: number): string {
  if (visitsAgo === 0) return "今回";
  if (visitsAgo === 1) return "前回";
  return `${visitsAgo}回前`;
}

function joinSoapEntries(
  entries: Array<{ text: string }> | undefined,
): string {
  if (!entries || entries.length === 0) return "";
  return entries
    .map((e) => e.text.trim())
    .filter(Boolean)
    .join(" / ");
}

export function CenterWorkspacePanel({
  activeMode,
  records,
  prescriptionsById,
  careEvents,
  selectedRecordId,
  onSelectRecord,
  newEntryHref,
  patientSummary,
  auditReport,
  auditLoading = false,
  auditError,
  onRunAudit,
}: CenterWorkspacePanelProps) {
  const [pageOffset, setPageOffset] = useState(0);
  const [institutionFilter, setInstitutionFilter] = useState<
    "all" | "same_as_latest"
  >("all");
  const [timelineOrder, setTimelineOrder] = useState<"desc" | "asc">("desc");

  const allPrescriptions = Object.values(prescriptionsById);
  const latestPrescription =
    [...allPrescriptions].sort((a, b) =>
      b.issued_date.localeCompare(a.issued_date),
    )[0] ?? null;

  if (activeMode === "past_history") {
    const latestRecordRxId = records[0]?.prescription_id ?? null;
    const latestInstitutionName = latestRecordRxId
      ? (prescriptionsById[latestRecordRxId]?.institution_name ?? null)
      : null;

    const filteredRecords =
      institutionFilter === "same_as_latest" && latestInstitutionName
        ? records.filter(
            (r) =>
              r.prescription_id &&
              prescriptionsById[r.prescription_id]?.institution_name ===
                latestInstitutionName,
          )
        : records;

    const windowSize = 3;
    const maxOffset = Math.max(0, filteredRecords.length - windowSize);
    const safeOffset = Math.min(pageOffset, maxOffset);
    const visibleRecords = filteredRecords.slice(
      safeOffset,
      safeOffset + windowSize,
    );
    // 左から古い順（2回前 → 前回 → 今回）になるよう並べる
    const chronologicalRecords = [...visibleRecords].reverse();
    const comparison = buildThreeVisitComparison(
      chronologicalRecords,
      prescriptionsById,
    );

    return (
      <Panel>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "6px",
            marginBottom: "6px",
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: "6px" }}>
            <Subheading>過去の処方・薬歴（直近3回比較）</Subheading>
            <MetaText>全 {filteredRecords.length} 件</MetaText>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "8px",
            }}
          >
            {latestInstitutionName ? (
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <Button
                  size="compact"
                  variant={institutionFilter === "all" ? "primary" : "secondary"}
                  onAction={() => {
                    setInstitutionFilter("all");
                    setPageOffset(0);
                  }}
                >
                  すべての医療機関
                </Button>
                <Button
                  size="compact"
                  variant={
                    institutionFilter === "same_as_latest"
                      ? "primary"
                      : "secondary"
                  }
                  onAction={() => {
                    setInstitutionFilter("same_as_latest");
                    setPageOffset(0);
                  }}
                >
                  今回と同じ医療機関のみ
                </Button>
              </div>
            ) : null}
            {filteredRecords.length > windowSize ? (
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Button
                  size="compact"
                  variant="secondary"
                  disabled={safeOffset >= maxOffset}
                  onAction={() =>
                    setPageOffset(Math.min(maxOffset, safeOffset + 1))
                  }
                >
                  ← 過去
                </Button>
                <MetaText>
                  {safeOffset + 1}〜{safeOffset + visibleRecords.length} /{" "}
                  {filteredRecords.length}
                </MetaText>
                <Button
                  size="compact"
                  variant="secondary"
                  disabled={safeOffset === 0}
                  onAction={() => setPageOffset(Math.max(0, safeOffset - 1))}
                >
                  最新 →
                </Button>
              </div>
            ) : null}
            <Link href={newEntryHref} appearance="action">
              ＋ 新規受付・処方登録
            </Link>
          </div>
        </div>

        {filteredRecords.length === 0 ? (
          <EmptyState>
            この患者の薬歴はまだ登録されていません。「新規受付・処方登録」から開始できます。
          </EmptyState>
        ) : (
          <>
            {comparison.summary.hasPrevious ? (
              <ContrastSummaryBanner
                hasChanges={!comparison.summary.isDoPrescription}
              >
                {comparison.summary.isDoPrescription ? (
                  <>
                    <ContrastStatusTag tone="slot">Do処方</ContrastStatusTag>
                    <span>前回処方から変更なし</span>
                  </>
                ) : (
                  <>
                    <span>前回からの変更:</span>
                    {comparison.summary.changedCount > 0 ? (
                      <ContrastStatusTag tone="changed">
                        用量・日数変更 {comparison.summary.changedCount}剤
                      </ContrastStatusTag>
                    ) : null}
                    {comparison.summary.addedCount > 0 ? (
                      <ContrastStatusTag tone="added">
                        新規追加 {comparison.summary.addedCount}剤
                      </ContrastStatusTag>
                    ) : null}
                    {comparison.summary.discontinuedCount > 0 ? (
                      <ContrastStatusTag tone="discontinued">
                        終了 {comparison.summary.discontinuedCount}剤
                      </ContrastStatusTag>
                    ) : null}
                  </>
                )}
              </ContrastSummaryBanner>
            ) : null}

            <ContrastMatrixFrame>
              {/* 列ヘッダー（固定3スロット: 2回前 / 前回 / 今回） */}
              <ContrastMatrixRow>
                {comparison.slots.map((record, colIdx) => {
                  const visitsAgo = safeOffset + (2 - colIdx);
                  const stepLabel = formatSlotStepLabel(visitsAgo);

                  if (!record) {
                    return (
                      <ContrastEmptySlotHeader
                        key={`empty-hdr-${colIdx}`}
                        label={stepLabel}
                        subLabel="履歴なし"
                      />
                    );
                  }

                  const isSelected = record.id === selectedRecordId;
                  const rx = record.prescription_id
                    ? prescriptionsById[record.prescription_id]
                    : undefined;

                  return (
                    <ContrastHeaderCell key={record.id} selected={isSelected}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          gap: "6px",
                          flexWrap: "wrap",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "4px",
                            fontSize: "12px",
                          }}
                        >
                          <ContrastStatusTag tone="slot">
                            {stepLabel}
                          </ContrastStatusTag>
                          <strong>
                            {formatDate(
                              record.counseled_at ?? record.event_occurred_at,
                            )}
                          </strong>
                          <Badge>
                            {STATUS_LABELS[record.status] ?? record.status}
                          </Badge>
                        </div>
                        <Button
                          size="compact"
                          variant={isSelected ? "primary" : "secondary"}
                          onAction={() => onSelectRecord(record.id)}
                        >
                          {isSelected ? "編集中" : "開く"}
                        </Button>
                      </div>
                      <div
                        style={{
                          fontSize: "11px",
                          color: "#4f6862",
                          overflowWrap: "anywhere",
                        }}
                      >
                        {rx
                          ? `${rx.institution_name}（${rx.document_number}）`
                          : "処方箋紐付けなし"}
                      </div>
                    </ContrastHeaderCell>
                  );
                })}
              </ContrastMatrixRow>

              {/* 用法グループ・薬剤対照行 */}
              {comparison.groups.map((group) => (
                <div key={group.key}>
                  <ContrastSectionBar>{group.label}</ContrastSectionBar>
                  {group.rows.map((row) => (
                    <ContrastMatrixRow key={row.key} bordered>
                      {row.cells.map((cell, colIdx) => {
                        const slotRecord = comparison.slots[colIdx];
                        if (!slotRecord) {
                          return (
                            <ContrastEmptySlotCell
                              key={`${row.key}-empty-${colIdx}`}
                            >
                              —
                            </ContrastEmptySlotCell>
                          );
                        }

                        const isSelected = slotRecord.id === selectedRecordId;
                        const hasPrevSlot =
                          colIdx > 0 && comparison.slots[colIdx - 1] !== null;

                        return (
                          <ContrastCell
                            key={`${row.key}-${colIdx}`}
                            selected={isSelected}
                          >
                            {cell.status === "absent" ? (
                              <span style={{ fontSize: "12px", color: "#4f6862" }}>
                                —
                              </span>
                            ) : cell.status === "discontinued" ? (
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: "1px",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "4px",
                                    flexWrap: "wrap",
                                  }}
                                >
                                  <ContrastStatusTag tone="discontinued">
                                    終了（前回あり）
                                  </ContrastStatusTag>
                                  <span
                                    style={{
                                      fontSize: "11.5px",
                                      color: "#4f6862",
                                      textDecoration: "line-through",
                                    }}
                                  >
                                    {cell.name}
                                  </span>
                                </div>
                                <div
                                  style={{
                                    fontSize: "11px",
                                    color: "#4f6862",
                                  }}
                                >
                                  前回: {cell.prevAmount}
                                  {cell.prevUnit} ・ {cell.prevQuantity}日分
                                </div>
                              </div>
                            ) : (
                              <>
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    gap: "4px",
                                    flexWrap: "wrap",
                                  }}
                                >
                                  <span
                                    style={{
                                      fontSize: "12px",
                                      fontWeight: 600,
                                      lineHeight: 1.3,
                                      color: "#18302e",
                                      overflowWrap: "anywhere",
                                    }}
                                  >
                                    {cell.name}
                                  </span>
                                  {cell.status === "added" ? (
                                    <ContrastStatusTag tone="added">
                                      新規
                                    </ContrastStatusTag>
                                  ) : cell.status === "changed" ? (
                                    <ContrastStatusTag tone="changed">
                                      変更
                                    </ContrastStatusTag>
                                  ) : hasPrevSlot ? (
                                    <ContrastStatusTag tone="unchanged">
                                      継続
                                    </ContrastStatusTag>
                                  ) : null}
                                </div>
                                <div
                                  style={{
                                    fontSize: "11px",
                                    lineHeight: 1.3,
                                    color: "#4f6862",
                                    marginTop: "1px",
                                  }}
                                >
                                  {cell.doseChanged ? (
                                    <ContrastDiffText>
                                      {cell.prevAmount}
                                      {cell.prevUnit} → {cell.amount}
                                      {cell.unit}
                                    </ContrastDiffText>
                                  ) : (
                                    <span>
                                      {cell.amount}
                                      {cell.unit}
                                    </span>
                                  )}
                                  {" ・ "}
                                  {cell.quantityChanged ? (
                                    <ContrastDiffText>
                                      {cell.prevQuantity}日分 → {cell.quantity}
                                      日分
                                    </ContrastDiffText>
                                  ) : (
                                    <span>{cell.quantity}日分</span>
                                  )}
                                </div>
                              </>
                            )}
                          </ContrastCell>
                        );
                      })}
                    </ContrastMatrixRow>
                  ))}
                </div>
              ))}

              {/* 薬歴（SOAP）要約対照行 */}
              <ContrastSectionBar>薬歴（SOAP要約）</ContrastSectionBar>
              <ContrastMatrixRow>
                {comparison.slots.map((record, colIdx) => {
                  if (!record) {
                    return (
                      <ContrastEmptySlotCell key={`soap-empty-${colIdx}`}>
                        —
                      </ContrastEmptySlotCell>
                    );
                  }
                  const isSelected = record.id === selectedRecordId;
                  const soap = record.effective_soap ?? record.soap;
                  const sText = joinSoapEntries(soap.subjective);
                  const oText = joinSoapEntries(soap.objective);
                  const aText = joinSoapEntries(soap.assessment);
                  const pText = joinSoapEntries(soap.plan);

                  return (
                    <ContrastCell key={`soap-${record.id}`} selected={isSelected}>
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "2px",
                          fontSize: "11px",
                          lineHeight: 1.35,
                          overflowWrap: "anywhere",
                        }}
                      >
                        {sText ? (
                          <p style={{ margin: 0 }}>
                            <strong>S:</strong> {sText}
                          </p>
                        ) : null}
                        {oText ? (
                          <p style={{ margin: 0 }}>
                            <strong>O:</strong> {oText}
                          </p>
                        ) : null}
                        {aText ? (
                          <p style={{ margin: 0 }}>
                            <strong>A:</strong> {aText}
                          </p>
                        ) : null}
                        {pText ? (
                          <p style={{ margin: 0 }}>
                            <strong>P:</strong> {pText}
                          </p>
                        ) : null}
                        {!sText && !oText && !aText && !pText ? (
                          <span style={{ color: "#4f6862" }}>
                            （SOAP記載なし）
                          </span>
                        ) : null}
                      </div>
                    </ContrastCell>
                  );
                })}
              </ContrastMatrixRow>
            </ContrastMatrixFrame>
          </>
        )}
      </Panel>
    );
  }

  if (activeMode === "patient_timeline") {
    const timelineEntries = buildTimelineEntries(
      records,
      careEvents,
      timelineOrder,
    );

    return (
      <Panel>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "6px",
            marginBottom: "6px",
          }}
        >
          <div>
            <Subheading>患者タイムライン</Subheading>
            <MetaText>
              来局・処方・薬歴の時系列経過（全 {timelineEntries.length} 件）
            </MetaText>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <Button
                size="compact"
                variant={timelineOrder === "desc" ? "primary" : "secondary"}
                onAction={() => setTimelineOrder("desc")}
              >
                新しい順
              </Button>
              <Button
                size="compact"
                variant={timelineOrder === "asc" ? "primary" : "secondary"}
                onAction={() => setTimelineOrder("asc")}
              >
                古い順
              </Button>
            </div>
            <Link href={newEntryHref} appearance="action">
              ＋ 新規受付・処方登録
            </Link>
          </div>
        </div>

        {timelineEntries.length === 0 ? (
          <EmptyState>来局・対応イベントはまだ登録されていません。</EmptyState>
        ) : (
          <TimelineList>
            {timelineEntries.map((entry, idx) => {
              const rx = entry.prescriptionId
                ? prescriptionsById[entry.prescriptionId]
                : undefined;
              const rec = entry.record;
              const isSelected = Boolean(rec && rec.id === selectedRecordId);
              const chronologicalIndexFromLatest =
                timelineOrder === "desc"
                  ? idx
                  : timelineEntries.length - 1 - idx;
              const stepLabel = formatSlotStepLabel(chronologicalIndexFromLatest);
              const soap = rec ? (rec.effective_soap ?? rec.soap) : null;
              const sText = soap ? joinSoapEntries(soap.subjective) : "";
              const oText = soap ? joinSoapEntries(soap.objective) : "";
              const aText = soap ? joinSoapEntries(soap.assessment) : "";
              const pText = soap ? joinSoapEntries(soap.plan) : "";

              return (
                <TimelineItem
                  key={entry.key}
                  dateLabel={formatDate(entry.occurredAt)}
                  stepLabel={stepLabel}
                  selected={isSelected}
                  isLatest={chronologicalIndexFromLatest === 0}
                  isLast={idx === timelineEntries.length - 1}
                  badges={
                    <>
                      <Badge>{entry.eventTypeName ?? "来局・調剤"}</Badge>
                      {rec ? (
                        <Badge>
                          {STATUS_LABELS[rec.status] ?? rec.status}
                        </Badge>
                      ) : null}
                    </>
                  }
                  subtitle={
                    rx
                      ? `${rx.institution_name}（処方箋: ${rx.document_number}）`
                      : undefined
                  }
                  headerActions={
                    rec ? (
                      <Button
                        size="compact"
                        variant={isSelected ? "primary" : "secondary"}
                        onAction={() => onSelectRecord(rec.id)}
                      >
                        {isSelected ? "編集中" : "右欄で開く"}
                      </Button>
                    ) : undefined
                  }
                  sections={[
                    {
                      title: "処方内容",
                      content:
                        rx && rx.rps.length > 0 ? (
                          <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                            {rx.rps.map((rp) => (
                              <div key={rp.rp_number}>
                                <div style={{ fontSize: "11px", color: "#4f6862", fontWeight: 600 }}>
                                  RP{rp.rp_number}: {rp.dosage_name || "用法未設定"}（{rp.quantity}日分）
                                </div>
                                <ul style={{ margin: "1px 0 0 14px", padding: 0, fontSize: "11.5px", lineHeight: 1.35 }}>
                                  {rp.medicines.map((m, mIdx) => (
                                    <li key={mIdx}>
                                      {m.name} {m.amount}
                                      {m.unit}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span style={{ fontSize: "11.5px", color: "#4f6862" }}>
                            処方情報なし
                          </span>
                        ),
                    },
                    {
                      title: "薬歴・指導要約（SOAP）",
                      content: rec ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px", fontSize: "11.5px", lineHeight: 1.35 }}>
                          {sText ? (
                            <p style={{ margin: 0 }}>
                              <strong>S:</strong> {sText}
                            </p>
                          ) : null}
                          {oText ? (
                            <p style={{ margin: 0 }}>
                              <strong>O:</strong> {oText}
                            </p>
                          ) : null}
                          {aText ? (
                            <p style={{ margin: 0 }}>
                              <strong>A:</strong> {aText}
                            </p>
                          ) : null}
                          {pText ? (
                            <p style={{ margin: 0 }}>
                              <strong>P:</strong> {pText}
                            </p>
                          ) : null}
                          {!sText && !oText && !aText && !pText ? (
                            <span style={{ color: "#4f6862" }}>
                              （SOAP記載なし）
                            </span>
                          ) : null}
                        </div>
                      ) : (
                        <span style={{ fontSize: "12px", color: "#4f6862" }}>
                          薬歴未作成
                        </span>
                      ),
                    },
                  ]}
                />
              );
            })}
          </TimelineList>
        )}
      </Panel>
    );
  }

  if (activeMode === "usage_history") {
    const usages = aggregateDrugUsage(allPrescriptions);
    return (
      <Panel>
        <Subheading>使用薬剤履歴</Subheading>
        <Paragraph>処方履歴から集計した薬剤ごとの累計処方日数・最新用法</Paragraph>
        {usages.length === 0 ? (
          <EmptyState>処方履歴がまだありません。</EmptyState>
        ) : (
          <Table aria-label="使用薬剤履歴">
            <thead>
              <tr>
                <TableHeader>薬剤名</TableHeader>
                <TableHeader>YJコード</TableHeader>
                <TableHeader>最新用法</TableHeader>
                <TableHeader>累計日数・回数</TableHeader>
                <TableHeader>処方回数</TableHeader>
                <TableHeader>最終処方日</TableHeader>
              </tr>
            </thead>
            <tbody>
              {usages.map((u) => (
                <tr key={u.key}>
                  <TableCell>{u.name}</TableCell>
                  <TableCell>{u.code}</TableCell>
                  <TableCell>{u.latestDosageName}</TableCell>
                  <TableCell>{u.totalQuantity} 日/回</TableCell>
                  <TableCell>{u.prescriptionCount} 回</TableCell>
                  <TableCell>{u.latestIssuedDate}</TableCell>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    );
  }

  if (activeMode === "patient_summary") {
    return (
      <Panel>
        <Subheading>患者サマリー</Subheading>
        <Paragraph>{patientSummary.patientName} さんの来局・臨床情報サマリー</Paragraph>
        <Cards>
          <div style={{ border: "1px solid #d7dce2", borderRadius: "8px", padding: "0.75rem" }}>
            <SectionHeading>基本・受診統計</SectionHeading>
            <Paragraph>生年月日: {patientSummary.birthDate ?? "—"}</Paragraph>
            <Paragraph>薬歴件数: {records.length} 件</Paragraph>
            <Paragraph>来局イベント: {careEvents.length} 件</Paragraph>
            <Paragraph>処方箋件数: {allPrescriptions.length} 件</Paragraph>
          </div>
          <div style={{ border: "1px solid #d7dce2", borderRadius: "8px", padding: "0.75rem" }}>
            <SectionHeading>臨床プロファイル登録状況</SectionHeading>
            <Paragraph>アレルギー: {patientSummary.allergiesCount} 件</Paragraph>
            <Paragraph>副作用歴: {patientSummary.sideEffectsCount} 件</Paragraph>
            <Paragraph>既往歴: {patientSummary.medicalHistoriesCount} 件</Paragraph>
            <Paragraph>併用薬: {patientSummary.concomitantMedsCount} 件</Paragraph>
          </div>
        </Cards>
      </Panel>
    );
  }

  if (activeMode === "audit_alerts") {
    return (
      <Panel>
        <Title>
          <div>
            <Subheading>処方監査・相互作用アラート</Subheading>
            <Paragraph>最新の処方箋に対して相互作用監査を実行できます</Paragraph>
          </div>
          {latestPrescription && onRunAudit ? (
            <Button
              disabled={auditLoading}
              onAction={() => onRunAudit(latestPrescription.id)}
            >
              {auditLoading ? "監査中..." : "相互作用監査を実行"}
            </Button>
          ) : null}
        </Title>
        {auditError ? <Alert tone="error">{auditError}</Alert> : null}
        {!latestPrescription ? (
          <EmptyState>監査対象の処方箋がまだありません。</EmptyState>
        ) : auditReport ? (
          <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.75rem" }}>
            <Row>
              <Badge>対象処方: {auditReport.documentNumber}</Badge>
              <Badge>組合せ数: {auditReport.totalCombinations}</Badge>
              <Badge>併用禁忌: {auditReport.contraindicatedCount} 件</Badge>
              <Badge>併用注意: {auditReport.precautionCount} 件</Badge>
            </Row>
            {auditReport.pairs.length === 0 ? (
              <Alert tone="info">
                相互作用アラート（併用禁忌・併用注意）は検出されませんでした。
              </Alert>
            ) : (
              <Cards>
                {auditReport.pairs.map((p, idx) => (
                  <Alert
                    key={idx}
                    tone={p.severity === "contraindicated" ? "error" : "info"}
                  >
                    <strong>
                      {p.first_name} × {p.second_name}（{p.severity}）
                    </strong>
                    : {p.description}
                  </Alert>
                ))}
              </Cards>
            )}
          </div>
        ) : (
          <EmptyState>
            「相互作用監査を実行」ボタンを押すと監査結果が表示されます。
          </EmptyState>
        )}
      </Panel>
    );
  }

  if (activeMode === "remaining_medication") {
    const withResidual = records.filter((r) => r.residual_drug !== null);
    return (
      <Panel>
        <Subheading>残薬確認</Subheading>
        <Paragraph>薬歴に記録された残薬状況・確認履歴</Paragraph>
        {withResidual.length === 0 ? (
          <EmptyState>
            残薬確認の記録はまだありません。右欄の「最終確認・確定」内の残薬確認ガイドから方針を記録できます。
          </EmptyState>
        ) : (
          <Cards>
            {withResidual.map((r) => (
              <div
                key={r.id}
                style={{
                  border: "1px solid #d7dce2",
                  borderRadius: "8px",
                  padding: "0.75rem",
                }}
              >
                <Row>
                  <strong>{formatDate(r.counseled_at ?? r.event_occurred_at)}</strong>
                  <Badge>残薬記録あり</Badge>
                </Row>
                <Paragraph>{JSON.stringify(r.residual_drug)}</Paragraph>
              </div>
            ))}
          </Cards>
        )}
      </Panel>
    );
  }

  return (
    <Panel>
      <Subheading>
        {activeMode === "questionnaire" ? "問診・薬歴入力" : "検査値・バイタル推移"}
      </Subheading>
      <Alert tone="info">
        この機能（{activeMode === "questionnaire" ? "問診票マスタ・回答比較" : "検査項目マスタ・検査値グラフ"}）は
        Phase 4 でバックエンドドメインと合わせて実装予定です。
      </Alert>
    </Panel>
  );
}
