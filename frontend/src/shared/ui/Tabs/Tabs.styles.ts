import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  tabs: {
    display: "flex",
    gap: tokens.spaceSm,
    flexWrap: "wrap",
    alignItems: "center",
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
    paddingBlock: tokens.spaceSm,
    marginBottom: tokens.spaceSm,
  },
});
