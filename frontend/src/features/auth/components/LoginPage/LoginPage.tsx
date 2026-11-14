import { useLogin } from "./useLogin";
import { LoginView } from "./LoginView";

export function LoginPage(props: {
  returnTo: string;
  navigate: (href: string) => Promise<void>;
}) {
  const state = useLogin(props.returnTo, props.navigate);
  return <LoginView {...state} />;
}
