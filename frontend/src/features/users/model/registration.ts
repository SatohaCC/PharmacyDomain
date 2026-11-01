import type { Submission } from "../../../shared/forms/submission";
export type UserRole = "corporate_admin" | "store_operator" | "store_viewer";

export type EmploymentType =
  | "regular"
  | "fixed_term"
  | "part_time"
  | "dispatched";

export const EMPLOYMENT_TYPE_LABELS: Record<string, string> = {
  regular: "正社員（常勤）",
  fixed_term: "契約社員",
  part_time: "パート・アルバイト（非常勤）",
  dispatched: "派遣スタッフ",
};

export const EMPLOYMENT_TYPE_OPTIONS = Object.entries(
  EMPLOYMENT_TYPE_LABELS,
).map(([value, label]) => ({ value, label }));

export const LEAVE_REASON_LABELS: Record<string, string> = {
  maternity: "産前産後休業",
  childcare: "育児休業",
  family_care: "介護休業",
  injury_illness: "傷病休職",
  other: "その他休職",
};

export const LEAVE_REASON_OPTIONS = Object.entries(LEAVE_REASON_LABELS).map(
  ([value, label]) => ({ value, label }),
);

export interface RegistrationOptions {
  stores: { id: string; name: string }[];
}
export interface RegistrationViewProps extends RegistrationOptions {
  corporateId: string;
  role: UserRole;
  setRole: (role: UserRole) => void;
  issued?: { id: string; email: string };
  registrationSubmission: Submission;
}
