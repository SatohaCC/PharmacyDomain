import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import {
  Title,
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  ActionRow,
  SpreadRow,
  ComparisonGrid,
  MetaText,
  Cards,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import { Link } from "../../../shared/ui/navigation/link";
import { Alert, EmptyState } from "../../../shared/ui/feedback/alert";
import type { MedicationHistoryDto } from "../api/record-api";
import {
  aggregateDrugUsage,
  type DetailFooterMode,
  type PrescriptionSummaryForHistory,
} from "../model/history-modes";

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

  const allPrescriptions = Object.values(prescriptionsById);
  const latestPrescription =
    [...allPrescriptions].sort((a, b) =>
      b.issued_date.localeCompare(a.issued_date),
    )[0] ?? null;

  if (activeMode === "past_history") {
    const windowSize = 3;
    const maxOffset = Math.max(0, records.length - windowSize);
    const safeOffset = Math.min(pageOffset, maxOffset);
    const visibleRecords = records.slice(safeOffset, safeOffset + windowSize);

    return (
      <Panel>
        <Title>
          <div>
            <Subheading>過去処方・薬歴（3列比較）</Subheading>
            <Paragraph>
              全 {records.length} 件の薬歴・処方内容を確認できます
            </Paragraph>
          </div>
          <Link href={newEntryHref} appearance="action">
            新規受付・処方登録
          </Link>
        </Title>

        {records.length > windowSize ? (
          <SpreadRow>
            <Button
              variant="secondary"
              disabled={safeOffset === 0}
              onAction={() => setPageOffset(Math.max(0, safeOffset - 1))}
            >
              ← 新しい履歴へ
            </Button>
            <MetaText>
              {safeOffset + 1}〜{safeOffset + visibleRecords.length} /{" "}
              {records.length} 件
            </MetaText>
            <Button
              variant="secondary"
              disabled={safeOffset >= maxOffset}
              onAction={() =>
                setPageOffset(Math.min(maxOffset, safeOffset + 1))
              }
            >
              古い履歴へ →
            </Button>
          </SpreadRow>
        ) : null}

        {records.length === 0 ? (
          <EmptyState>
            この患者の薬歴はまだ登録されていません。「新規受付・処方登録」から開始できます。
          </EmptyState>
        ) : (
          <ComparisonGrid>
            {visibleRecords.map((record) => {
              const isSelected = record.id === selectedRecordId;
              const soap = record.effective_soap ?? record.soap;
              const sText = joinSoapEntries(soap.subjective);
              const oText = joinSoapEntries(soap.objective);
              const aText = joinSoapEntries(soap.assessment);
              const pText = joinSoapEntries(soap.plan);
              const rx = record.prescription_id
                ? prescriptionsById[record.prescription_id]
                : undefined;

              return (
                <article
                  key={record.id}
                  style={{
                    border: "1px solid #d0ddd8",
                    boxShadow: isSelected
                      ? "0 0 0 2px #176b60"
                      : "0 1px 3px rgba(32, 60, 57, 0.05)",
                    borderRadius: "10px",
                    padding: "0.875rem",
                    backgroundColor: isSelected ? "#f0fdfa" : "#ffffff",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.5rem",
                    minWidth: 0,
                  }}
                >
                  <ActionRow>
                    <strong>
                      {formatDate(record.counseled_at ?? record.event_occurred_at)}
                    </strong>
                    <Badge>
                      {STATUS_LABELS[record.status] ?? record.status}
                    </Badge>
                  </ActionRow>

                  {rx ? (
                    <div
                      style={{
                        backgroundColor: "#f8fafc",
                        borderRadius: "6px",
                        padding: "0.5rem",
                        fontSize: "0.8125rem",
                      }}
                    >
                      <div>
                        <strong>{rx.institution_name}</strong>（{rx.document_number}）
                      </div>
                      {rx.rps.map((rp) => (
                        <div key={rp.rp_number} style={{ marginTop: "0.25rem" }}>
                          <div>
                            Rp{rp.rp_number}: {rp.dosage_name} / {rp.quantity}日分
                          </div>
                          <ul style={{ margin: "0.125rem 0 0 1rem", padding: 0 }}>
                            {rp.medicines.map((m, idx) => (
                              <li key={idx}>
                                {m.name} {m.amount}
                                {m.unit}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  <div
                    style={{
                      display: "grid",
                      gap: "0.25rem",
                      fontSize: "0.875rem",
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
                      <p style={{ margin: 0, color: "#6b7280" }}>
                        （SOAP記載なし）
                      </p>
                    ) : null}
                  </div>

                  <div style={{ marginTop: "auto" }}>
                    <Button
                      variant={isSelected ? "primary" : "secondary"}
                      onAction={() => onSelectRecord(record.id)}
                    >
                      {isSelected ? "右欄で編集中" : "右欄で開く"}
                    </Button>
                  </div>
                </article>
              );
            })}
          </ComparisonGrid>
        )}
      </Panel>
    );
  }

  if (activeMode === "patient_timeline") {
    return (
      <Panel>
        <Title>
          <div>
            <Subheading>患者タイムライン</Subheading>
            <Paragraph>来局・受付・薬歴作成の時系列履歴（{careEvents.length} 件）</Paragraph>
          </div>
          <Link href={newEntryHref} appearance="action">
            新規受付・処方登録
          </Link>
        </Title>
        {careEvents.length === 0 ? (
          <EmptyState>来局・対応イベントはまだ登録されていません。</EmptyState>
        ) : (
          <Cards>
            {careEvents.map((ev) => {
              const rx = ev.prescription_id
                ? prescriptionsById[ev.prescription_id]
                : undefined;
              return (
                <div
                  key={ev.event_id}
                  style={{
                    border: "1px solid #d7dce2",
                    borderRadius: "8px",
                    padding: "0.75rem",
                  }}
                >
                  <Row>
                    <strong>{formatDate(ev.occurred_at)}</strong>
                    <Badge>{ev.event_type_name ?? "対応イベント"}</Badge>
                  </Row>
                  {rx ? (
                    <Paragraph>
                      処方箋: {rx.document_number} / {rx.institution_name}（
                      {rx.rps.flatMap((r) => r.medicines.map((m) => m.name)).join("・")}）
                    </Paragraph>
                  ) : null}
                  {ev.medication_history_id ? (
                    <Button
                      variant="secondary"
                      onAction={() => {
                        if (ev.medication_history_id) {
                          onSelectRecord(ev.medication_history_id);
                        }
                      }}
                    >
                      この薬歴を右欄で開く
                    </Button>
                  ) : null}
                </div>
              );
            })}
          </Cards>
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
