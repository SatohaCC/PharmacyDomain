import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
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
const styles = stylex.create({
  panel: {
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.panelRadius,
    padding: {
      default: tokens.spaceLg,
      "@media (max-width: 750px)": tokens.spaceMd,
    },
    marginTop: tokens.spaceMd,
    boxShadow: tokens.shadow,
    overflowX: "auto",
  },
  stack: { display: "flex", flexDirection: "column" },
  small: { gap: tokens.spaceXs },
  normal: { gap: tokens.spaceMd },
  large: { gap: tokens.spaceLg },
});
