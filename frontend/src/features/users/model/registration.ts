import type { Submission } from "../../../shared/forms/submission";
export type UserRole = "corporate_admin" | "store_operator" | "store_viewer";
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
