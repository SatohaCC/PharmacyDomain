import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  panel: {
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.panelRadius,
    padding: {
      default: "10px 12px",
      "@media (max-width: 750px)": "8px 10px",
    },
    boxShadow: tokens.shadow,
    overflowX: "auto",
  },
  stack: { display: "flex", flexDirection: "column" },
  small: { gap: "6px" },
  normal: { gap: "8px" },
  large: { gap: "12px" },
});
