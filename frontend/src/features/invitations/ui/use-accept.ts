import { useSubmission } from "../../../shared/forms/use-submission";
import { useState } from "react";
import { acceptInvitation, acceptedActor } from "../api/invitation-api";
import { ApiError } from "../../../shared/api/errors";
import { readInvitation } from "../../../shared/navigation/paths";

import { text } from "../../../shared/forms/values";

export interface AcceptanceAuth {
  authenticated: boolean;
  oidcAvailable: boolean;
  login: () => Promise<void>;
}
export function useAccept(auth: AcceptanceAuth) {
  const [secret] = useState(readInvitation);
  const [done, setDone] = useState(false);
  const [corporate, setCorporate] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [uncertain, setUncertain] = useState(false);

  const loginSubmission = () => auth.login();
  const acceptanceSubmission = async (d: FormData) => {
    if (uncertain)
      throw new Error(
        "前回の結果が不明です。再ログインして利用権限と招待状態を管理者へ確認してください。",
      );
    if (!auth.authenticated)
      throw new Error("先に本人確認のためログインしてください。");
    if (!accepted) {
      try {
        await acceptInvitation(text(d, "secret"));
        setAccepted(true);
      } catch (error) {
        if (error instanceof ApiError && error.uncertain) setUncertain(true);
        throw error;
      }
    }
    const actor = await acceptedActor();
    setCorporate(
      actor.roles.includes("corporate_admin") ? actor.corporate_id : null,
    );
    setDone(true);
  };
  return {
    secret,
    done,
    corporate,
    accepted,
    uncertain,
    loginSubmission: useSubmission(loginSubmission),
    acceptanceSubmission: useSubmission(acceptanceSubmission),
    oidcAvailable: auth.oidcAvailable,
    authenticated: !!auth.authenticated,
  };
}
