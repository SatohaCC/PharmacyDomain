import { useState } from "react";
import { registrationInput } from "../model/registration-input";
import type { UserRole } from "../model/registration";
import { useSubmission } from "../../../shared/forms/use-submission";
import { registerUser } from "../api/registration-api";

export function useUserRegistration(corporateId: string) {
  const [role, setRole] = useState<UserRole>("corporate_admin");
  const [issued, setIssued] = useState<{ id: string; email: string }>();
  const registrationSubmission = useSubmission(async (data: FormData) => {
    setIssued(
      await registerUser(corporateId, registrationInput(data, role), role),
    );
  });
  return { role, setRole, issued, registrationSubmission };
}
