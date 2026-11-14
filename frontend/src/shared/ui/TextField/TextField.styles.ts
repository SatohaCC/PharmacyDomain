import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  field: {
    display: "flex",
    flexDirection: "column",
    gap: "3px",
    marginBottom: "8px",
    maxWidth: tokens.formWidth,
  },
  label: {
    fontSize: tokens.fontSm,
    fontWeight: tokens.fontStrong,
    color: tokens.text,
  },
  required: {
    fontSize: tokens.fontSm,
    marginLeft: tokens.spaceXs,
    color: tokens.danger,
  },
  input: {
    width: "100%",
    minWidth: 0,
    minHeight: "32px",
    fontSize: "13px",
    paddingBlock: "4px",
    paddingInline: "8px",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: {
      default: tokens.border,
      ":hover": tokens.muted,
      ":user-invalid": tokens.danger,
    },
    borderRadius: tokens.radius,
    backgroundColor: tokens.surface,
    color: tokens.text,
    transition: "border-color 150ms ease",
    outline: {
      default: "none",
      ":focus-visible": `2px solid ${tokens.action}`,
    },
    outlineOffset: "2px",
  },
  description: {
    fontSize: tokens.fontSm,
    color: tokens.muted,
  },
  error: {
    fontSize: tokens.fontSm,
    color: tokens.danger,
    fontWeight: tokens.fontStrong,
  },
});
