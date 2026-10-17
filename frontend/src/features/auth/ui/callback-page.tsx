import { useAuthCallback } from "./use-callback";
import { CallbackView } from "./callback-view";
export function CallbackPage(props: {
  navigate: (href: string) => Promise<void>;
}) {
  const state = useAuthCallback(props.navigate);
  return <CallbackView {...state} />;
}
