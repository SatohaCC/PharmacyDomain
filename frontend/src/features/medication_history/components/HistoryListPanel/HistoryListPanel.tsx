import { Panel } from "../../../../shared/ui/Panel";
import { Badge } from "../../../../shared/ui/Badge";
import {
  Title,
  Subheading,
  Paragraph,
  Row,
  Cards,
} from "../../../../shared/ui/Elements";
import { Button } from "../../../../shared/ui/Button";
import { Link } from "../../../../shared/ui/Link";
import { EmptyState } from "../../../../shared/ui/Alert";
import type { MedicationHistoryDto } from "../../api/record-api";

export interface MedicationHistoryListPanelProps {
  records: MedicationHistoryDto[];
  selectedRecordId: string | null;
  onSelectRecord: (recordId: string) => void;
  newEntryHref?: string;
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

/** 患者の過去〜今回の薬歴一覧を中央ペインに表示する。 */
export function MedicationHistoryListPanel({
  records,
  selectedRecordId,
  onSelectRecord,
  newEntryHref,
}: MedicationHistoryListPanelProps) {
  return (
    <Panel>
      <Title>
        <div>
          <Subheading>薬歴・経過一覧</Subheading>
          <Paragraph>
            選択した薬歴を右欄で編集・確認できます（全 {records.length} 件）
          </Paragraph>
        </div>
        {newEntryHref ? (
          <Link href={newEntryHref} appearance="action">
            新規受付・処方登録
          </Link>
        ) : null}
      </Title>

      {records.length === 0 ? (
        <EmptyState>
          この患者の薬歴はまだ登録されていません。
        </EmptyState>
      ) : (
        <Cards>
          {records.map((record) => {
            const isSelected = record.id === selectedRecordId;
            const soap = record.effective_soap ?? record.soap;
            const sText = joinSoapEntries(soap.subjective);
            const oText = joinSoapEntries(soap.objective);
            const aText = joinSoapEntries(soap.assessment);
            const pText = joinSoapEntries(soap.plan);
            const dateLabel = formatDate(
              record.counseled_at ?? record.event_occurred_at,
            );
            return (
              <div
                key={record.id}
                style={{
                  border: isSelected
                    ? "2px solid #0f766e"
                    : "1px solid #d7dce2",
                  borderRadius: "8px",
                  padding: "0.75rem",
                  backgroundColor: isSelected ? "#f0fdfa" : "#ffffff",
                }}
              >
                <Row>
                  <strong>{dateLabel}</strong>
                  <Badge>
                    {STATUS_LABELS[record.status] ?? record.status}
                  </Badge>
                  {record.event_type_name ? (
                    <Badge>{record.event_type_name}</Badge>
                  ) : null}
                </Row>

                <div
                  style={{
                    marginTop: "0.5rem",
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

                <div style={{ marginTop: "0.75rem" }}>
                  <Button
                    variant={isSelected ? "primary" : "secondary"}
                    onAction={() => onSelectRecord(record.id)}
                  >
                    {isSelected ? "右欄で編集中" : "右欄で開く"}
                  </Button>
                </div>
              </div>
            );
          })}
        </Cards>
      )}
    </Panel>
  );
}
