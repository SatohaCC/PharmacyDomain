import { useEffect, useRef, type ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
export function Alert({
  children,
  tone = "error",
  focus = false,
}: {
  children: ReactNode;
  tone?: "error" | "info";
  focus?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focus) ref.current?.focus();
  }, [focus]);
  return (
    <div
      ref={ref}
      tabIndex={focus ? -1 : undefined}
      role={tone === "error" ? "alert" : "status"}
      {...stylex.props(styles.base, tone === "error" && styles.error)}
    >
      {children}
    </div>
  );
}
export function EmptyState({
  children = "登録はありません。",
}: {
  children?: ReactNode;
}) {
  return <p {...stylex.props(styles.empty)}>{children}</p>;
}
const styles = stylex.create({
  base: {
    padding: "6px 10px",
    marginBlock: "6px",
    fontSize: "12px",
    borderRadius: tokens.radius,
    backgroundColor: tokens.canvas,
    overflowWrap: "anywhere",
  },
  error: {
    color: tokens.danger,
    backgroundColor: tokens.dangerSurface,
    borderInlineStartWidth: "3px",
    borderInlineStartStyle: "solid",
    borderInlineStartColor: tokens.danger,
  },
  empty: {
    textAlign: "center",
    padding: "14px",
    fontSize: "12px",
    color: tokens.muted,
  },
});
