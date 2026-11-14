import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  card: {
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: { default: tokens.border, ":hover": tokens.action },
    borderRadius: tokens.panelRadius,
    padding: tokens.spaceMd,
    boxShadow: tokens.shadow,
    transition: "border-color 150ms ease, box-shadow 150ms ease, transform 150ms ease",
    transform: { default: "none", ":hover": "translateY(-1px)" },
  },
  description: {
    display: "block",
    color: tokens.muted,
    fontSize: tokens.fontSm,
    marginTop: tokens.spaceXs,
  },
});
