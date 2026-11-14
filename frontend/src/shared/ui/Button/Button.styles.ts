import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  base: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: tokens.spaceXs,
    width: "fit-content",
    minHeight: "28px",
    paddingBlock: "3px",
    paddingInline: "10px",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: "transparent",
    borderRadius: tokens.radius,
    fontSize: "12px",
    lineHeight: "1.2",
    fontWeight: tokens.fontStrong,
    whiteSpace: "nowrap",
    cursor: { default: "pointer", ":disabled": "not-allowed" },
    color: tokens.onAction,
    backgroundColor: { default: tokens.action, ":hover": tokens.actionHover },
    transition: "background-color 150ms ease, border-color 150ms ease, transform 100ms ease",
    transform: { default: "none", ":active": "translateY(1px)" },
    outline: { default: "none", ":focus-visible": `3px solid ${tokens.focus}` },
    outlineOffset: "3px",
    opacity: { default: 1, ":disabled": tokens.disabledOpacity },
  },
  compact: {
    minHeight: "24px",
    paddingBlock: "2px",
    paddingInline: "8px",
    fontSize: "11px",
  },
  secondary: {
    color: tokens.action,
    borderColor: tokens.border,
    backgroundColor: { default: tokens.surface, ":hover": tokens.surfaceSubtle },
  },
});
