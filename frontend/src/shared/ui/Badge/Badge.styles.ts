import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  badge: {
    display: "inline-flex",
    alignItems: "center",
    fontSize: "11px",
    fontWeight: tokens.fontStrong,
    lineHeight: "1.25",
    backgroundColor: tokens.surfaceSubtle,
    color: tokens.text,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: "999px",
    paddingBlock: "1px",
    paddingInline: "6px",
    whiteSpace: "nowrap",
  },
});
