import { useAccept, type AcceptanceAuth } from "./use-accept";
import { AcceptView } from "./accept-view";
export function AcceptPage({ auth }: { auth: AcceptanceAuth }) {
  const state = useAccept(auth);
  return <AcceptView {...state} />;
}
