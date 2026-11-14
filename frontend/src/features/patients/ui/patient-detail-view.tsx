import { useState } from "react";
import { Panel, Stack } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  PropertyList,
  PropertyRow,
  CompactInfoCard,
} from "../../../shared/ui/data-display/property-list";
import {
  Title,
  Subheading,
  SectionHeading,
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

function calculateAge(birthDate: string | null): number | null {
  if (!birthDate) return null;
  const parsed = new Date(birthDate);
  if (Number.isNaN(parsed.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - parsed.getFullYear();
  const monthDiff = today.getMonth() - parsed.getMonth();
  if (
    monthDiff < 0 ||
    (monthDiff === 0 && today.getDate() < parsed.getDate())
  ) {
    age -= 1;
  }
  return age >= 0 ? age : null;
}

export interface PatientDetailViewProps {
  patient: PatientDetail;
  heading?: PatientHeading | null;
  headingFetchError?: string | null;
  medicalProfile?: PatientMedicalProfile | null;
  medicalProfileFetchError?: string | null;
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
  headingFetchError,
  medicalProfile,
  medicalProfileFetchError,
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

  const age = calculateAge(patient.birth_date);

  return (
    <Stack gap="small">
      {/* 基本情報パネル（Yakureki左ペイン相当のコンパクトなキー・バリュー一覧） */}
      <Panel>
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "6px",
            paddingBottom: "5px",
            marginBottom: "4px",
            borderBottom: "1px solid #d0ddd8",
          }}
        >
          <div style={{ minWidth: 0 }}>
            <Subheading>
              {patient.last_name} {patient.first_name}
            </Subheading>
            <div style={{ fontSize: "11.5px", color: "#4f6862" }}>
              {patient.last_name_kana} {patient.first_name_kana}
            </div>
          </div>
          <Badge>{PATIENT_STATUS_LABELS[patient.status] || patient.status}</Badge>
        </div>

        {patient.merged_into_id && (
          <Alert tone="info">
            この患者は統合されています（統合先ID: {patient.merged_into_id}）。
          </Alert>
        )}

        <PropertyList>
          <PropertyRow label="患者番号" value={`#${patient.patient_number}`} />
          <PropertyRow
            label="生年月日"
            value={
              patient.birth_date
                ? age !== null
                  ? `${patient.birth_date} (${age}歳)`
                  : patient.birth_date
                : "—"
            }
          />
          <PropertyRow
            label="性別"
            value={patient.gender ? GENDER_LABELS[patient.gender] || patient.gender : "—"}
          />
          <PropertyRow
            label="郵便番号"
            value={patient.postal_code ? `〒${patient.postal_code}` : "—"}
          />
          <PropertyRow label="住所" value={patient.address || "—"} />
          <PropertyRow label="電話番号" value={patient.phone_number || "—"} isLast />
        </PropertyList>
      </Panel>

      {/* 臨床プロファイル（薬歴からの投影）パネル — 医療安全上最優先のため基本情報の直下に配置 */}
      {(medicalProfile || medicalProfileFetchError) && (
        <Panel>
          <SectionHeading>臨床プロファイル（薬歴投影）</SectionHeading>
          {medicalProfileFetchError ? (
            <div style={{ marginTop: "6px" }}>
              <Alert tone="error">
                臨床プロファイルの取得に失敗しました: {medicalProfileFetchError}
              </Alert>
            </div>
          ) : medicalProfile ? (
            <Stack gap="small">
              <CompactInfoCard
                title="アレルギー"
                tone={medicalProfile.allergies.length > 0 ? "alert" : "default"}
              >
                {medicalProfile.allergies.length > 0 ? (
                  <ul style={{ margin: 0, paddingInlineStart: "16px", lineHeight: 1.35 }}>
                    {medicalProfile.allergies.map((a, i) => (
                      <li key={i}>
                        {a.allergen} {a.reaction && `(${a.reaction})`}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ color: "#4f6862", margin: 0 }}>特記事項なし</p>
                )}
              </CompactInfoCard>

              <CompactInfoCard
                title="副作用歴"
                tone={
                  medicalProfile.adverse_reactions.length > 0
                    ? "alert"
                    : "default"
                }
              >
                {medicalProfile.adverse_reactions.length > 0 ? (
                  <ul style={{ margin: 0, paddingInlineStart: "16px", lineHeight: 1.35 }}>
                    {medicalProfile.adverse_reactions.map((r, i) => (
                      <li key={i}>
                        {r.medicine_name} {r.symptom && `(${r.symptom})`}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ color: "#4f6862", margin: 0 }}>特記事項なし</p>
                )}
              </CompactInfoCard>

              <CompactInfoCard title="既往歴">
                {medicalProfile.medical_conditions.length > 0 ? (
                  <ul style={{ margin: 0, paddingInlineStart: "16px", lineHeight: 1.35 }}>
                    {medicalProfile.medical_conditions.map((c, i) => (
                      <li key={i}>
                        {c.condition_name} ({c.condition_status})
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ color: "#4f6862", margin: 0 }}>特記事項なし</p>
                )}
              </CompactInfoCard>

              <CompactInfoCard title="継続中の併用薬">
                {medicalProfile.active_concurrent_medications.length > 0 ? (
                  <ul style={{ margin: 0, paddingInlineStart: "16px", lineHeight: 1.35 }}>
                    {medicalProfile.active_concurrent_medications.map(
                      (m, i) => (
                        <li key={i}>
                          {m.medicine_name} ({m.category})
                        </li>
                      ),
                    )}
                  </ul>
                ) : (
                  <p style={{ color: "#4f6862", margin: 0 }}>特記事項なし</p>
                )}
              </CompactInfoCard>
            </Stack>
          ) : null}
        </Panel>
      )}

      {/* 自由記載の頭書きパネル */}
      <Panel>
        <Title>
          <SectionHeading>自由記載の頭書き（店舗共有）</SectionHeading>
          {onUpdateHeading && heading && patient.status !== "merged" && !isEditingHeading && (
            <Button
              variant="secondary"
              size="compact"
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

        {headingFetchError ? (
          <div style={{ marginBlock: "6px" }}>
            <Alert tone="error">
              頭書き情報の取得に失敗しました: {headingFetchError}
            </Alert>
          </div>
        ) : (
          <>
            {headingError && <Alert tone="error">{headingError}</Alert>}

            {isEditingHeading ? (
              <form onSubmit={handleHeadingSubmit} style={{ marginTop: "6px" }}>
                <FieldGroup>
                  <FieldLabel htmlFor="heading-summary">サマリ（概要）</FieldLabel>
                  <TextArea
                    id="heading-summary"
                    rows={2}
                    value={summaryInput}
                    onChange={(e) => setSummaryInput(e.target.value)}
                    placeholder="患者の概要や主要な留意点を入力"
                  />
                </FieldGroup>
                <FieldGroup>
                  <FieldLabel htmlFor="heading-notes">申し送り・特記事項</FieldLabel>
                  <TextArea
                    id="heading-notes"
                    rows={3}
                    value={notesInput}
                    onChange={(e) => setNotesInput(e.target.value)}
                    placeholder="店舗スタッフ間での申し送り、服薬指導上の注意点などを入力"
                  />
                </FieldGroup>
                <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
                  <Button type="submit" variant="primary" size="compact" disabled={savingHeading}>
                    {savingHeading ? "保存中..." : "頭書きを保存"}
                  </Button>
                  <Button
                    variant="secondary"
                    size="compact"
                    disabled={savingHeading}
                    onAction={() => setIsEditingHeading(false)}
                  >
                    キャンセル
                  </Button>
                </div>
              </form>
            ) : (
              <div>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginBlock: "6px", fontSize: "12px", lineHeight: 1.4 }}>
                  <div>
                    <span style={{ fontSize: "11.5px", color: "#4f6862", fontWeight: 600, display: "block", marginBottom: "2px" }}>
                      サマリ
                    </span>
                    <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                      {heading?.summary || "（未登録）"}
                    </p>
                  </div>
                  <div>
                    <span style={{ fontSize: "11.5px", color: "#4f6862", fontWeight: 600, display: "block", marginBottom: "2px" }}>
                      申し送り・特記事項
                    </span>
                    <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                      {heading?.notes || "（未登録）"}
                    </p>
                  </div>
                </div>
                {heading && (
                  <small style={{ color: "#4f6862", fontSize: "11px" }}>
                    改訂: {heading.revision} / 更新:{" "}
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
                    marginTop: "4px",
                    display: "flex",
                    flexDirection: "column",
                    gap: "6px",
                    borderInlineStart: "2px solid #e5e7eb",
                    paddingInlineStart: "8px",
                  }}
                >
                  {heading.history.map((rev) => (
                    <div key={rev.revision} style={{ fontSize: "11.5px", lineHeight: 1.35 }}>
                      <div>
                        <strong>改訂 #{rev.revision}</strong>
                        <span style={{ color: "#4f6862", marginLeft: "6px" }}>
                          {rev.recorded_at ? new Date(rev.recorded_at).toLocaleString("ja-JP") : "—"}
                        </span>
                      </div>
                      {rev.summary && <p style={{ margin: "2px 0" }}>サマリ: {rev.summary}</p>}
                      {rev.notes && <p style={{ margin: "2px 0" }}>特記事項: {rev.notes}</p>}
                    </div>
                  ))}
                </div>
              </Details>
            )}
          </>
        )}
      </Panel>
    </Stack>
  );
}
