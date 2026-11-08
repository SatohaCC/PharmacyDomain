/** 薬歴確定と最終確認のフロントエンド契約。 */

export type MedicationHistoryReviewResult =
  | "assessment_and_instruction_recorded"
  | "no_additional_recordable_items";

export interface FinalizeMedicationHistoryInput {
  counseled_at?: string | null;
  event_occurred_at?: string | null;
  delay_reason?: string | null;
  review_result: MedicationHistoryReviewResult;
}

export interface PendingExternalCorrectionSummary {
  correction_id: string;
  reason: string;
  status: string;
}

export type ResidualGuidanceLevel =
  | "confirm_usage"
  | "review_cause"
  | "coordinate_with_prescriber";

export const RESIDUAL_GUIDANCE_OPTIONS: {
  value: ResidualGuidanceLevel;
  label: string;
  description: string;
}[] = [
  {
    value: "confirm_usage",
    label: "服薬状況を確認する",
    description:
      "飲み忘れ、使用状況、保管状態を聞き取り、確認した内容を薬歴へ記録します。",
  },
  {
    value: "review_cause",
    label: "残薬の発生要因を確認する",
    description:
      "服薬環境や困りごとを確認し、患者に合う再発防止策を検討します。",
  },
  {
    value: "coordinate_with_prescriber",
    label: "処方医との連携を検討する",
    description:
      "処方内容の相談が必要と判断した場合は、患者の意向を確認して処方医へ情報共有し、対応を記録します。",
  },
];
