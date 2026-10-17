import { useSubmission } from "../../../shared/forms/use-submission";
import { text } from "../../../shared/forms/values";
import { login, oidc, setAccessToken } from "../api/session";

export function useLogin(
  returnTo: string,
  navigate: (href: string) => Promise<void>,
) {
  const loginSubmission = () => login(returnTo);
  const tokenSubmission = async (d: FormData) => {
    setAccessToken(text(d, "token"));
    await navigate(returnTo);
  };
  return {
    loginSubmission: useSubmission(loginSubmission),
    tokenSubmission: useSubmission(tokenSubmission),
    oidcAvailable: !!oidc(),
    authenticated: false,
  };
}
