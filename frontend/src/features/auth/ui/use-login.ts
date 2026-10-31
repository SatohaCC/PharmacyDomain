import { useSubmission } from "../../../shared/forms/use-submission";
import { text } from "../../../shared/forms/values";
import { setAccessToken } from "../api/session";
import {
  passwordLogin,
  changeInitialPassword,
} from "../api/local-authentication";
import { useRef, useState } from "react";

export function useLogin(
  returnTo: string,
  navigate: (href: string) => Promise<void>,
) {
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
      : await passwordLogin(
          text(d, "corporate_id"),
          text(d, "email"),
          password,
        );
    if (session.password_change_required) {
      restrictedToken.current = session.access_token;
      setPasswordChangeRequired(true);
    } else {
      restrictedToken.current = "";
      setAccessToken(session.access_token);
      await navigate(returnTo);
    }
  };
  const tokenSubmission = async (d: FormData) => {
    setAccessToken(text(d, "token"));
    await navigate(returnTo);
  };
  return {
    loginSubmission: useSubmission(loginSubmission),
    tokenSubmission: useSubmission(tokenSubmission),
    passwordChangeRequired,
    authenticated: false,
  };
}
