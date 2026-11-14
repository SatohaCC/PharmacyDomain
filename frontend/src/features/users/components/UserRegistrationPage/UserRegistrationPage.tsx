import { useUserRegistration } from "./useUserRegistration";
import { UserRegistrationView } from "./UserRegistrationView";
import type { RegistrationOptions } from "../../model/registration";

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
