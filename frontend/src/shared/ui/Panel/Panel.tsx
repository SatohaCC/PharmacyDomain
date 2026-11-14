import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./Panel.styles";

export function Panel({
  children,
  title,
}: {
  children: ReactNode;
  title?: string;
}) {
  return (
    <section {...stylex.props(styles.panel)}>
      {title && <h2>{title}</h2>}
      {children}
    </section>
  );
}
export function Stack({
  children,
  gap = "normal",
}: {
  children: ReactNode;
  gap?: "small" | "normal" | "large";
}) {
  return <div {...stylex.props(styles.stack, styles[gap])}>{children}</div>;
}
