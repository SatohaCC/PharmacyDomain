import { useAuthCallback } from "./useCallback";
import { CallbackView } from "./CallbackView";

export function CallbackPage(props: {
  navigate: (href: string) => Promise<void>;
}) {
  const state = useAuthCallback(props.navigate);
  return <CallbackView {...state} />;
}
