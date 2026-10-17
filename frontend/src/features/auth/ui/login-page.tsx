import { useLogin } from "./use-login";
import { LoginView } from "./login-view";
export function LoginPage(props: {
  returnTo: string;
  navigate: (href: string) => Promise<void>;
}) {
  const state = useLogin(props.returnTo, props.navigate);
  return <LoginView {...state} />;
}
