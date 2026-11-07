import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  Title,
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  Cards,
  Details,
  Summary,
  FieldGroup,
  FieldLabel,
  TextArea,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import { Alert } from "../../../shared/ui/feedback/alert";
import {
  type PatientDetail,
  type PatientHeading,
  type PatientMedicalProfile,
  PATIENT_STATUS_LABELS,
  GENDER_LABELS,
} from "../model/patient";

export interface PatientDetailViewProps {
  patient: PatientDetail;
  heading?: PatientHeading | null;
  medicalProfile?: PatientMedicalProfile | null;
  storeId: string;
  onUpdateHeading?: (input: {
    expectedRevision: number;
    summary: string | null;
    notes: string | null;
  }) => Promise<void>;
}

export function PatientDetailView({
  patient,
  heading,
  medicalProfile,
  onUpdateHeading,
}: PatientDetailViewProps) {
  const [isEditingHeading, setIsEditingHeading] = useState(false);
  const [summaryInput, setSummaryInput] = useState(heading?.summary ?? "");
  const [notesInput, setNotesInput] = useState(heading?.notes ?? "");
  const [savingHeading, setSavingHeading] = useState(false);
  const [headingError, setHeadingError] = useState<string | null>(null);

  const handleHeadingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!onUpdateHeading || !heading) return;
    setSavingHeading(true);
    setHeadingError(null);
    try {
      await onUpdateHeading({
        expectedRevision: heading.revision,
        summary: summaryInput || null,
        notes: notesInput || null,
      });
      setIsEditingHeading(false);
    } catch (err) {
      setHeadingError(
        err instanceof Error ? err.message : "頭書きの更新に失敗しました。",
      );
    } finally {
      setSavingHeading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* 基本情報パネル */}
      <Panel>
        <Title>
          <div>
            <Subheading>
              {patient.last_name} {patient.first_name}
              <span
                style={{
                  fontSize: "14px",
                  color: "#6b7280",
                  fontWeight: "normal",
                  marginLeft: "0.5rem",
                }}
              >
                （{patient.last_name_kana} {patient.first_name_kana}）
              </span>
            </Subheading>
            <Paragraph>患者番号: #{patient.patient_number}</Paragraph>
          </div>
          <Badge>{PATIENT_STATUS_LABELS[patient.status] || patient.status}</Badge>
        </Title>

        {patient.merged_into_id && (
          <Alert tone="info">
            この患者は統合されています（統合先ID: {patient.merged_into_id}）。
          </Alert>
        )}

        <Row>
          <div>
            <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              生年月日
            </span>
            <p>{patient.birth_date || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              性別
            </span>
            <p>{patient.gender ? GENDER_LABELS[patient.gender] || patient.gender : "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              電話番号
            </span>
            <p>{patient.phone_number || "—"}</p>
          </div>
          <div>
            <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              郵便番号
            </span>
            <p>{patient.postal_code ? `〒${patient.postal_code}` : "—"}</p>
          </div>
        </Row>
        {patient.address && (
          <div style={{ marginTop: "1rem" }}>
            <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
              住所
            </span>
            <p>{patient.address}</p>
          </div>
        )}
      </Panel>

      {/* 自由記載の頭書きパネル */}
      <Panel>
        <Title>
          <div>
            <SectionHeading>自由記載の頭書き（店舗共有申し送り）</SectionHeading>
            <Paragraph>
              患者全体の留意点・サマリ・申し送り事項です。全店舗で共有されます。
            </Paragraph>
          </div>
          {onUpdateHeading && heading && patient.status !== "merged" && !isEditingHeading && (
            <Button
              variant="secondary"
              onAction={() => {
                setSummaryInput(heading.summary ?? "");
                setNotesInput(heading.notes ?? "");
                setIsEditingHeading(true);
              }}
            >
              頭書きを編集
            </Button>
          )}
        </Title>

        {headingError && <Alert tone="error">{headingError}</Alert>}

        {isEditingHeading ? (
          <form onSubmit={handleHeadingSubmit} style={{ marginTop: "1rem" }}>
            <FieldGroup>
              <FieldLabel htmlFor="heading-summary">サマリ（概要）</FieldLabel>
              <TextArea
                id="heading-summary"
                rows={3}
                value={summaryInput}
                onChange={(e) => setSummaryInput(e.target.value)}
                placeholder="患者の概要や主要な留意点を入力"
              />
            </FieldGroup>
            <FieldGroup>
              <FieldLabel htmlFor="heading-notes">申し送り・特記事項</FieldLabel>
              <TextArea
                id="heading-notes"
                rows={4}
                value={notesInput}
                onChange={(e) => setNotesInput(e.target.value)}
                placeholder="店舗スタッフ間での申し送り、服薬指導上の注意点などを入力"
              />
            </FieldGroup>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
              <Button type="submit" variant="primary" disabled={savingHeading}>
                {savingHeading ? "保存中..." : "頭書きを保存"}
              </Button>
              <Button
                variant="secondary"
                disabled={savingHeading}
                onAction={() => setIsEditingHeading(false)}
              >
                キャンセル
              </Button>
            </div>
          </form>
        ) : (
          <div>
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBlock: "1rem" }}>
              <div>
                <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
                  サマリ
                </span>
                <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                  {heading?.summary || "（未登録）"}
                </p>
              </div>
              <div>
                <span style={{ fontSize: "14px", color: "#6b7280", fontWeight: "bold", display: "block", marginBottom: "0.25rem" }}>
                  申し送り・特記事項
                </span>
                <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                  {heading?.notes || "（未登録）"}
                </p>
              </div>
            </div>
            {heading && (
              <small style={{ color: "#6b7280" }}>
                改訂: {heading.revision} / 最終更新日時:{" "}
                {heading.updated_at
                  ? new Date(heading.updated_at).toLocaleString("ja-JP")
                  : "—"}
              </small>
            )}
          </div>
        )}

        {heading?.history && heading.history.length > 0 && (
          <Details>
            <Summary>改訂履歴を表示（{heading.history.length}件）</Summary>
            <div
              style={{
                marginTop: "0.5rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
                borderInlineStart: "2px solid #e5e7eb",
                paddingInlineStart: "1rem",
              }}
            >
              {heading.history.map((rev) => (
                <div key={rev.revision} style={{ fontSize: "14px" }}>
                  <div>
                    <strong>改訂 #{rev.revision}</strong>
                    <span style={{ color: "#6b7280", marginLeft: "0.5rem" }}>
                      {rev.recorded_at ? new Date(rev.recorded_at).toLocaleString("ja-JP") : "—"}
                    </span>
                  </div>
                  {rev.summary && <p style={{ margin: "0.25rem 0" }}>サマリ: {rev.summary}</p>}
                  {rev.notes && <p style={{ margin: "0.25rem 0" }}>特記事項: {rev.notes}</p>}
                </div>
              ))}
            </div>
          </Details>
        )}
      </Panel>

      {/* 臨床プロファイル（薬歴からの投影）パネル */}
      {medicalProfile && (
        <Panel>
          <SectionHeading>臨床プロファイル（薬歴投影）</SectionHeading>
          <Paragraph>薬歴から自動構築された臨床情報の現在値です。</Paragraph>

          <Cards>
            <div style={{ padding: "1rem", border: "1px solid #e5e7eb", borderRadius: "8px" }}>
              <strong style={{ display: "block", marginBottom: "0.5rem" }}>アレルギー</strong>
              {medicalProfile.allergies.length > 0 ? (
                <ul style={{ margin: 0, paddingInlineStart: "1.25rem" }}>
                  {medicalProfile.allergies.map((a, i) => (
                    <li key={i}>{a.allergen} {a.reaction && `(${a.reaction})`}</li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "#6b7280", margin: 0 }}>特記事項なし</p>
              )}
            </div>

            <div style={{ padding: "1rem", border: "1px solid #e5e7eb", borderRadius: "8px" }}>
              <strong style={{ display: "block", marginBottom: "0.5rem" }}>副作用歴</strong>
              {medicalProfile.adverse_reactions.length > 0 ? (
                <ul style={{ margin: 0, paddingInlineStart: "1.25rem" }}>
                  {medicalProfile.adverse_reactions.map((r, i) => (
                    <li key={i}>{r.medicine_name} {r.symptom && `(${r.symptom})`}</li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "#6b7280", margin: 0 }}>特記事項なし</p>
              )}
            </div>

            <div style={{ padding: "1rem", border: "1px solid #e5e7eb", borderRadius: "8px" }}>
              <strong style={{ display: "block", marginBottom: "0.5rem" }}>既往歴</strong>
              {medicalProfile.medical_conditions.length > 0 ? (
                <ul style={{ margin: 0, paddingInlineStart: "1.25rem" }}>
                  {medicalProfile.medical_conditions.map((c, i) => (
                    <li key={i}>{c.condition_name} ({c.condition_status})</li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "#6b7280", margin: 0 }}>特記事項なし</p>
              )}
            </div>

            <div style={{ padding: "1rem", border: "1px solid #e5e7eb", borderRadius: "8px" }}>
              <strong style={{ display: "block", marginBottom: "0.5rem" }}>継続中の併用薬</strong>
              {medicalProfile.active_concurrent_medications.length > 0 ? (
                <ul style={{ margin: 0, paddingInlineStart: "1.25rem" }}>
                  {medicalProfile.active_concurrent_medications.map((m, i) => (
                    <li key={i}>{m.medicine_name} ({m.category})</li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "#6b7280", margin: 0 }}>特記事項なし</p>
              )}
            </div>
          </Cards>
        </Panel>
      )}
    </div>
  );
}
