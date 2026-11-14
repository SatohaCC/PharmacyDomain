import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
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
