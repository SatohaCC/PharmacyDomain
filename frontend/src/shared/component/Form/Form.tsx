import type { ReactNode } from "react";
import { AriaForm } from "../../ui/Form";
import { Button } from "../../ui/Button";
import { Alert } from "../../ui/Alert";

export interface FormProps {
  children?: ReactNode;
  onSubmit: (data: FormData) => void;
  label?: string;
  pendingLabel?: string;
  blockedLabel?: string;
  loginLabel?: string;
  pending?: boolean;
  blocked?: boolean;
  error?: string;
  onLogin?: () => void;
}
export function Form({
  children,
  onSubmit,
  label = "登録する",
  pendingLabel = "処理中…",
  blockedLabel = "処理結果を確認してください",
  loginLabel = "ログイン画面へ",
  pending,
  blocked,
  error,
  onLogin,
}: FormProps) {
  return (
    <AriaForm
      onSubmit={(e) => {
        e.preventDefault();
        if (!pending && !blocked) onSubmit(new FormData(e.currentTarget));
      }}
    >
      {error && (
        <Alert key={error} focus>
          {error}
          {onLogin && (
            <p>
              <Button variant="secondary" onAction={onLogin}>
                {loginLabel}
              </Button>
            </p>
          )}
        </Alert>
      )}
      <fieldset
        aria-busy={pending || undefined}
        disabled={pending || blocked}
        onKeyDown={(e) => {
          if (
            e.key === "Enter" &&
            (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229)
          )
            e.preventDefault();
        }}
      >
        {children}
        <Button type="submit" disabled={blocked} pending={pending}>
          {blocked ? blockedLabel : pending ? pendingLabel : label}
        </Button>
      </fieldset>
    </AriaForm>
  );
}
