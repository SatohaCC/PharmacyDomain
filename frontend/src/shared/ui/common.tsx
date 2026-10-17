import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { ApiError, errorText } from "../api/client";
export function ErrorNotice({ error }: { error: unknown }) {
  return error ? (
    <div role="alert" className="notice error">
      {errorText(error)}
      {error instanceof ApiError && error.status === 401 && (
        <p>
          <a href="/login">ログイン画面へ</a>
        </p>
      )}
    </div>
  ) : null;
}
export function Form({
  children,
  onSubmit,
  label = "登録する",
}: {
  children?: ReactNode;
  onSubmit: (data: FormData) => Promise<void>;
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState<unknown>();
  const lock = useRef(false);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (lock.current || uncertain) return;
    lock.current = true;
    setBusy(true);
    setError(undefined);
    const data = new FormData(e.currentTarget);
    try {
      await onSubmit(data);
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && e.uncertain) setUncertain(true);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <ErrorNotice error={error} />
      <fieldset disabled={busy || uncertain}>
        {children}
        <button type="submit">
          {uncertain ? "処理結果を確認してください" : busy ? "処理中…" : label}
        </button>
      </fieldset>
    </form>
  );
}
export function Field({
  name,
  label,
  required = false,
  type = "text",
  defaultValue,
  readOnly = false,
}: {
  name: string;
  label: string;
  required?: boolean;
  type?: string;
  defaultValue?: string;
  readOnly?: boolean;
}) {
  return (
    <label className="field">
      {label}
      {required && <span className="required">必須</span>}
      <input
        name={name}
        type={type}
        required={required}
        defaultValue={defaultValue}
        readOnly={readOnly}
      />
    </label>
  );
}
export const text = (data: FormData, key: string) =>
  String(data.get(key) || "").trim();
export const optional = (data: FormData, key: string) =>
  text(data, key) || null;
export function Empty({
  children = "登録はありません。",
}: {
  children?: ReactNode;
}) {
  return <p className="empty">{children}</p>;
}
