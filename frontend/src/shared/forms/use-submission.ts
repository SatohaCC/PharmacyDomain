import { useEffect, useRef, useState } from "react";
import { ApiError, errorText } from "../api/errors";
export function useSubmission(onSubmit: (data: FormData) => Promise<void>) {
  const lock = useRef(false);
  const [pending, setPending] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [error, setError] = useState<string>();
  const [requiresLogin, setRequiresLogin] = useState(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  // 別画面への移動後に以前の処理で画面状態を変更しない。
  const submit = async (data: FormData) => {
    if (lock.current || blocked) return;
    lock.current = true;
    setPending(true);
    setError(undefined);
    setRequiresLogin(false);
    try {
      await onSubmit(data);
    } catch (e) {
      if (active.current) {
        setError(errorText(e));
        setRequiresLogin(e instanceof ApiError && e.status === 401);
        if (e instanceof ApiError && e.uncertain) setBlocked(true);
      }
    } finally {
      lock.current = false;
      if (active.current) setPending(false);
    }
  };
  return {
    pending,
    blocked,
    error,
    requiresLogin,
    submit,
    onLogin: requiresLogin ? () => location.assign("/login") : undefined,
  };
}
