import { useSubmission } from "../../../shared/forms/use-submission";
import { text } from "../../../shared/forms/values";
import { currentActor } from "../api/actor-api";
import { setAccessToken } from "../api/session";
import {
  passwordLogin,
  vendorPasswordLogin,
  changeInitialPassword,
} from "../api/local-authentication";
import { useRef, useState } from "react";

export function useLogin(
  returnTo: string,
  navigate: (href: string) => Promise<void>,
) {
  const [loginKind, setLoginKind] = useState("corporate");
  const restrictedToken = useRef("");
  const [passwordChangeRequired, setPasswordChangeRequired] = useState(false);
  const loginSubmission = async (d: FormData) => {
    setAccessToken("");
    const password = String(d.get("password") || "");
    if (
      passwordChangeRequired &&
      password !== String(d.get("confirmation") || "")
    )
      throw new Error("確認用パスワードが一致しません。");
    const session = passwordChangeRequired
      ? await changeInitialPassword(restrictedToken.current, password)
      : loginKind === "vendor"
        ? await vendorPasswordLogin(text(d, "login_id"), password)
        : await passwordLogin(
            text(d, "corporate_code"),
            text(d, "login_id"),
            password,
          );
    if (session.password_change_required) {
      restrictedToken.current = session.access_token;
      setPasswordChangeRequired(true);
    } else {
      restrictedToken.current = "";
      setAccessToken(session.access_token);
      let target =
        returnTo === "/admin" && loginKind === "corporate" ? "/" : returnTo;
      if (loginKind === "corporate" && returnTo.startsWith("/admin/")) {
        const actor = await currentActor().catch(() => null);
        const canAccessAdmin =
          actor?.roles.includes("corporate_admin") ||
          actor?.roles.includes("vendor_system_admin");
        if (!canAccessAdmin) {
          target = "/";
        }
      }
      await navigate(target);
    }
  };
  const tokenSubmission = async (d: FormData) => {
    setAccessToken(text(d, "token"));
    const target = returnTo === "/admin" ? "/" : returnTo;
    await navigate(target);
  };
  return {
    loginKind,
    setLoginKind,
    loginSubmission: useSubmission(loginSubmission),
    tokenSubmission: useSubmission(tokenSubmission),
    passwordChangeRequired,
    authenticated: false,
  };
}
