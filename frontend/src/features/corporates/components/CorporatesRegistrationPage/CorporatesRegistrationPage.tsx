import { CorporateRegistrationView } from "./CorporatesRegistrationView";
import { useCorporateRegistration } from "./useCorporatesRegistration";

export function CorporateRegistrationPage(props: {
  onComplete: (id: string) => Promise<void>;
}) {
  const { submit } = useCorporateRegistration(props);
  return <CorporateRegistrationView onSubmit={submit} />;
}
