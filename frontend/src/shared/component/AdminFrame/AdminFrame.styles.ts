import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  shell: {
    display: "grid",
    gridTemplateColumns: {
      default: "256px minmax(0,1fr)",
      "@media (max-width: 750px)": "1fr",
    },
    minBlockSize: "100dvh",
  },
  aside: {
    backgroundColor: tokens.surface,
    padding: tokens.spaceMd,
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceMd,
    position: { default: "sticky", "@media (max-width: 750px)": "static" },
    insetBlockStart: 0,
    alignSelf: "start",
    blockSize: { default: "100dvh", "@media (max-width: 750px)": "auto" },
    overflowY: { default: "auto", "@media (max-width: 750px)": "visible" },
    borderInlineEndWidth: tokens.borderWidth,
    borderInlineEndStyle: "solid",
    borderInlineEndColor: tokens.border,
  },
  brand: {
    fontSize: "21px",
    fontWeight: tokens.fontStrong,
    letterSpacing: "-0.01em",
    color: tokens.text,
    textDecoration: "none",
  },
  menu: { margin: 0 },
  menuSummary: {
    fontSize: tokens.fontSm,
    fontWeight: tokens.fontStrong,
    color: tokens.muted,
    letterSpacing: "0.04em",
    marginBlockStart: 0,
    marginBlockEnd: tokens.spaceSm,
  },
  navigation: { display: "flex", flexDirection: "column", gap: tokens.spaceXs },
  footnote: {
    marginBlockStart: "auto",
    color: tokens.muted,
    fontSize: "12px",
    lineHeight: "1.5",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: tokens.spaceSm,
    paddingBlockEnd: tokens.spaceMd,
    marginBlockEnd: tokens.spaceMd,
    borderBlockEndWidth: tokens.borderWidth,
    borderBlockEndStyle: "solid",
    borderBlockEndColor: tokens.border,
  },
});
