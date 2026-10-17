import { invitationInput } from "../model/invitation-input";
import { useLeaveWarning } from "../../../shared/navigation/leaving";
import { useSubmission } from "../../../shared/forms/use-submission";
import { issueInvitation, invitationStatus } from "../api/registration-api";
import { useRef, useState } from "react";
import type { RegistrationProgress } from "../model/prepare-invitation";

import { useEffect } from "react";

export function useUserRegistration(corporateId: string) {
  const [personMode, setPersonMode] = useState("new");
  const [role, setRole] = useState<
    "corporate_admin" | "store_operator" | "store_viewer"
  >("corporate_admin");
  const [staffMode, setStaffMode] = useState("existing");
  const progress = useRef<RegistrationProgress>({});
  const [snapshot, setSnapshot] = useState<RegistrationProgress>({});
  const changed = () => setSnapshot({ ...progress.current });
  const [issued, setIssued] = useState<{ id: string; secret: string }>();
  const [status, setStatus] = useState("");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string>();
  const [frozen, setFrozen] = useState(false);

  const statusSubmission = async () => {
    if (!issued) return;
    const detail = await invitationStatus(corporateId, issued.id);
    setStatus(detail.status);
  };
  const invitationSubmission = async (d: FormData) => {
    setFrozen(true);
    try {
      setIssued(
        await issueInvitation(
          corporateId,
          invitationInput(d, role, new Date()),
          personMode,
          role,
          staffMode,
          progress.current,
          changed,
        ),
      );
    } finally {
      if (!progress.current.personId && !progress.current.uncertain)
        setFrozen(false);
    }
  };
  const copyInvitation = async () => {
    if (!issued) return;
    try {
      await navigator.clipboard.writeText(
        location.origin +
          "/invitations/accept#secret=" +
          encodeURIComponent(issued.secret),
      );
      setCopied(true);
      setCopyError(undefined);
    } catch {
      setCopyError(
        "コピーできませんでした。招待URLを選択して手動でコピーしてください。",
      );
    }
  };
  useEffect(() => {
    if (!issued) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [issued]);
  useLeaveWarning(
    !!issued,
    "招待URLは再表示できません。コピー済みか確認してから移動してください。",
  );
  return {
    copyError,
    invitationUrl: issued
      ? location.origin +
        "/invitations/accept#secret=" +
        encodeURIComponent(issued.secret)
      : undefined,
    personMode,
    setPersonMode,
    role,
    setRole,
    staffMode,
    setStaffMode,
    snapshot,
    issued,
    status,
    copied,
    frozen,
    statusSubmission: useSubmission(statusSubmission),
    invitationSubmission: useSubmission(invitationSubmission),
    copyInvitation,
  };
}
