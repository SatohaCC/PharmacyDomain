import { useState } from "react";
import { Alert } from "../../../shared/ui/feedback/alert";
import {
  FieldGroup,
  FieldLabel,
  Paragraph,
  SectionHeading,
  TextArea,
} from "../../../shared/ui/layout/elements";
import { Button } from "../../../shared/ui/controls/button";
import type {
  FinalizeMedicationHistoryInput,
  MedicationHistoryReviewResult,
  PendingExternalCorrectionSummary,
  ResidualGuidanceLevel,
} from "../model/finalization";
import { RESIDUAL_GUIDANCE_OPTIONS } from "../model/finalization";

export interface FinalizationReviewPanelProps {
  isDraft: boolean;
  hasUnsavedChanges: boolean;
  delayReasonRequired?: boolean;
  pendingExternalCorrections?: PendingExternalCorrectionSummary[];
  advisoryWarnings?: string[];
  onFinalize: (input: FinalizeMedicationHistoryInput) => Promise<unknown>;
  onResidualGuidanceChange?: (level: ResidualGuidanceLevel) => void;
}

export function FinalizationReviewPanel({
  isDraft,
  hasUnsavedChanges,
  delayReasonRequired = false,
  pendingExternalCorrections = [],
  advisoryWarnings = [],
  onFinalize,
  onResidualGuidanceChange,
}: FinalizationReviewPanelProps) {
  const [reviewResult, setReviewResult] =
    useState<MedicationHistoryReviewResult | null>(null);
  const [delayReason, setDelayReason] = useState("");
  const [guidanceLevel, setGuidanceLevel] =
    useState<ResidualGuidanceLevel>("confirm_usage");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const canFinalize =
    isDraft &&
    !hasUnsavedChanges &&
    pendingExternalCorrections.length === 0 &&
    reviewResult !== null &&
    (!delayReasonRequired || delayReason.trim().length > 0) &&
    !submitting;

  const handleFinalize = async () => {
    if (!canFinalize || reviewResult === null) return;
    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const input: FinalizeMedicationHistoryInput = {
        review_result: reviewResult,
        ...(delayReason.trim() ? { delay_reason: delayReason.trim() } : {}),
      };
      await onFinalize(input);
      setSuccessMessage("薬歴を確定しました。");
    } catch (error: unknown) {
      setErrorMessage(
        error instanceof Error ? error.message : "薬歴の確定に失敗しました。",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section aria-label="薬歴の最終確認" style={{ marginTop: "1.5rem" }}>
      <SectionHeading>最終確認・確定</SectionHeading>

      <section
        aria-label="残薬確認ガイド"
        style={{
          border: "1px solid #d7dce2",
          borderRadius: "8px",
          padding: "1rem",
          marginTop: "0.75rem",
        }}
      >
        <h3 style={{ marginTop: 0 }}>残薬確認ガイド</h3>
        <Paragraph>
          状況に応じて確認の進め方を選択してください。数量による自動判定は行いません。
        </Paragraph>
        <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
          <legend>確認の進め方</legend>
          <div style={{ display: "grid", gap: "0.75rem", marginTop: "0.5rem" }}>
            {RESIDUAL_GUIDANCE_OPTIONS.map((option) => (
              <label
                key={option.value}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1.25rem 1fr",
                  columnGap: "0.5rem",
                  alignItems: "start",
                  padding: "0.75rem",
                  border: "1px solid #d7dce2",
                  borderRadius: "6px",
                }}
              >
                <input
                  type="radio"
                  name="residual-guidance-level"
                  value={option.value}
                  checked={guidanceLevel === option.value}
                  onChange={() => {
                    setGuidanceLevel(option.value);
                    onResidualGuidanceChange?.(option.value);
                  }}
                />
                <span>
                  <strong>{option.label}</strong>
                  <span style={{ display: "block", marginTop: "0.25rem" }}>
                    {option.description}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      {pendingExternalCorrections.length > 0 && (
        <section role="alert" aria-label="未解決の外部訂正">
          <strong>未解決の外部訂正があるため確定できません。</strong>
          <ul>
            {pendingExternalCorrections.map((correction) => (
              <li key={correction.correction_id}>
                {correction.reason}（{correction.status}）
              </li>
            ))}
          </ul>
        </section>
      )}

      {advisoryWarnings.length > 0 && (
        <section aria-label="確認事項" style={{ marginTop: "1rem" }}>
          <h3>確認事項</h3>
          <Paragraph>
            内容を確認してください。これらの補助情報だけでは確定を妨げません。
          </Paragraph>
          <ul>
            {advisoryWarnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      <fieldset
        disabled={!isDraft || submitting}
        style={{ border: 0, padding: 0, marginTop: "1rem" }}
      >
        <legend>薬歴の確認結果</legend>
        <div style={{ display: "grid", gap: "0.5rem", marginTop: "0.5rem" }}>
          <label>
            <input
              type="radio"
              name="medication-history-review-result"
              checked={
                reviewResult === "assessment_and_instruction_recorded"
              }
              onChange={() =>
                setReviewResult("assessment_and_instruction_recorded")
              }
            />
            薬学的評価と指導内容を記録した
          </label>
          <label>
            <input
              type="radio"
              name="medication-history-review-result"
              checked={reviewResult === "no_additional_recordable_items"}
              onChange={() =>
                setReviewResult("no_additional_recordable_items")
              }
            />
            追加して記録すべき事項がないことを確認した
          </label>
        </div>
      </fieldset>

      <FieldGroup style={{ marginTop: "1rem" }}>
        <FieldLabel htmlFor="medication-history-delay-reason">
          記載遅延理由{delayReasonRequired ? "（必須）" : "（任意）"}
        </FieldLabel>
        <TextArea
          id="medication-history-delay-reason"
          value={delayReason}
          disabled={!isDraft || submitting}
          rows={2}
          onChange={(event) => setDelayReason(event.target.value)}
          placeholder="指導日と異なる日に確定する場合は理由を入力してください"
        />
      </FieldGroup>

      {hasUnsavedChanges && (
        <Paragraph role="status">
          未保存の変更があります。先に下書きを保存してください。
        </Paragraph>
      )}
      {errorMessage && <Alert tone="error">{errorMessage}</Alert>}
      {successMessage && <Alert tone="info">{successMessage}</Alert>}

      {isDraft && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <Button
            variant="primary"
            pending={submitting}
            disabled={!canFinalize}
            onAction={() => void handleFinalize()}
          >
            薬歴を確定
          </Button>
        </div>
      )}
    </section>
  );
}
