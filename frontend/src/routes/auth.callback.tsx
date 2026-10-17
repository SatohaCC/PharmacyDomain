import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { oidc, setAccessToken } from "../shared/auth/session";
import { safeReturnPath } from "../shared/api/client";
import { ErrorNotice } from "../shared/ui/common";
export const Route = createFileRoute("/auth/callback")({ component: Callback });
function Callback() {
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>();
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
        await navigate({ href: safeReturnPath(state?.returnTo) });
      })
      .catch((e) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
    };
  }, [navigate]);
  return (
    <main className="entry">
      <h1>ログインの確認</h1>
      <ErrorNotice
        error={
          error || (!oidc() ? new Error("OIDC接続先が未設定です。") : undefined)
        }
      />
      {!error && <p role="status">確認中…</p>}
      <a href="/login">ログインへ戻る</a>
    </main>
  );
}
