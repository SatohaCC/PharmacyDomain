import { Form as AriaForm } from "react-aria-components";
import type { ReactNode } from "react";
import { Button } from "./button";
import { Alert } from "../feedback/alert";
export interface FormProps {
  children?: ReactNode;
  onSubmit: (data: FormData) => void;
  label?: string;
  pending?: boolean;
  blocked?: boolean;
  error?: string;
  onLogin?: () => void;
}
export function Form({
  children,
  onSubmit,
  label = "登録する",
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
                ログイン画面へ
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
          {blocked ? "処理結果を確認してください" : pending ? "処理中…" : label}
        </Button>
      </fieldset>
    </AriaForm>
  );
}
