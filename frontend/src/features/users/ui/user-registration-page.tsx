import { useUserRegistration } from "./use-user-registration";
import { UserRegistrationView } from "./user-registration-view";
import type { RegistrationOptions } from "../model/registration";
export function UserRegistrationPage({
  corporateId,
  options,
}: {
  corporateId: string;
  options: RegistrationOptions;
}) {
  const state = useUserRegistration(corporateId);
  return (
    <UserRegistrationView corporateId={corporateId} {...options} {...state} />
  );
}
