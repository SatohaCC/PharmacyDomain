import { CorporateRegistrationView } from "./corporates-registration-view";
import { useCorporateRegistration } from "./use-corporates-registration";
export function CorporateRegistrationPage(props: {
  onComplete: (id: string) => Promise<void>;
}) {
  const { submit } = useCorporateRegistration(props);
  return <CorporateRegistrationView onSubmit={submit} />;
}
