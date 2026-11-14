import { useEffect, useRef, type ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./Alert.styles";

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
export function EmptyState({ children }: { children: ReactNode }) {
  return <p {...stylex.props(styles.empty)}>{children}</p>;
}
