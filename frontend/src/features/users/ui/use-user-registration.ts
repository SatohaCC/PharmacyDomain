import { registrationInput } from "../model/registration-input";
import { useSubmission } from "../../../shared/forms/use-submission";
import { registerUser } from "../api/registration-api";
import { useRef, useState } from "react";
import type { RegistrationProgress } from "../model/prepare-registration";

export function useUserRegistration(corporateId: string) {
  const [personMode, setPersonMode] = useState("new");
  const [role, setRole] = useState<
    "corporate_admin" | "store_operator" | "store_viewer"
  >("corporate_admin");
  const [staffMode, setStaffMode] = useState("existing");
  const progress = useRef<RegistrationProgress>({});
  const [snapshot, setSnapshot] = useState<RegistrationProgress>({});
  const changed = () => setSnapshot({ ...progress.current });
  const [issued, setIssued] = useState<{ id: string; login_id: string }>();
  const [frozen, setFrozen] = useState(false);
  const registrationSubmission = async (d: FormData) => {
    setFrozen(true);
    try {
      setIssued(
        await registerUser(
          corporateId,
          registrationInput(d, role),
          personMode,
          role,
          staffMode,
          progress.current,
          changed,
        ),
      );
    } finally {
      if (!progress.current.personId && !progress.current.uncertain)
        setFrozen(false);
    }
  };
  return {
    personMode,
    setPersonMode,
    role,
    setRole,
    staffMode,
    setStaffMode,
    snapshot,
    issued,
    frozen,
    registrationSubmission: useSubmission(registrationSubmission),
  };
}
