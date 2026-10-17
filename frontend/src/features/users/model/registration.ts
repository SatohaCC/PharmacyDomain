import type { Submission } from "../../../shared/forms/submission";
import type { RegistrationProgress } from "./prepare-invitation";
export type UserRole = "corporate_admin" | "store_operator" | "store_viewer";
export interface RegistrationOptions {
  stores: { id: string; name: string }[];
  staffs: {
    id: string;
    is_active: boolean;
    last_name: string;
    first_name: string;
  }[];
}
export interface RegistrationViewProps extends RegistrationOptions {
  corporateId: string;
  personMode: string;
  setPersonMode: (mode: string) => void;
  role: UserRole;
  setRole: (role: UserRole) => void;
  staffMode: string;
  setStaffMode: (mode: string) => void;
  snapshot: RegistrationProgress;
  issued?: { id: string; secret: string };
  status: string;
  copyError?: string;
  invitationUrl?: string;
  copied: boolean;
  frozen: boolean;
  statusSubmission: Submission;
  invitationSubmission: Submission;
  copyInvitation: () => Promise<void>;
}
