import { StoreRegistrationView } from "./StoresRegistrationView";
import { useStoreRegistration } from "./useStoresRegistration";

export function StoreRegistrationPage(props: {
  corporateId: string;
  onComplete: () => Promise<void>;
}) {
  const { submit } = useStoreRegistration(props);
  return <StoreRegistrationView onSubmit={submit} />;
}
