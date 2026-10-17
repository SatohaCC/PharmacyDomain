import { useEffect, useState } from "react";
import { oidc, setAccessToken } from "../api/session";
import { safeReturnPath } from "../../../shared/navigation/paths";
import { errorText } from "../../../shared/api/errors";
export function useAuthCallback(navigate: (href: string) => Promise<void>) {
  const [error, setError] = useState<string>();
  useEffect(() => {
    let active = true;
    const manager = oidc();
    if (!manager) return;
    manager
      .signinRedirectCallback()
      .then(async (user) => {
        if (!active) return;
        setAccessToken(user.access_token);
        history.replaceState(null, "", "/auth/callback");
        const state = user.state as { returnTo?: unknown } | undefined;
        await navigate(safeReturnPath(state?.returnTo));
      })
      .catch((e) => {
        if (active) setError(errorText(e));
      });
    return () => {
      active = false;
    };
  }, [navigate]);
  return { error: error || (!oidc() ? "OIDC接続先が未設定です。" : undefined) };
}
