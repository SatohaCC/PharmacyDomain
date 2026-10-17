import { StoreRegistrationView } from "./stores-registration-view";
import { useStoreRegistration } from "./use-stores-registration";
export function StoreRegistrationPage(props: {
  corporateId: string;
  onComplete: () => Promise<void>;
}) {
  const { submit } = useStoreRegistration(props);
  return <StoreRegistrationView onSubmit={submit} />;
}
