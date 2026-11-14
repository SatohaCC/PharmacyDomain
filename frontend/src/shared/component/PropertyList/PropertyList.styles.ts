import * as stylex from "@stylexjs/stylex";
import { tokens } from "../../theme/tokens.stylex";

export const styles = stylex.create({
  list: {
    margin: 0,
    display: "flex",
    flexDirection: "column",
  },
  row: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: tokens.spaceXs,
    paddingBlock: "3px",
    fontSize: "12px",
  },
  rowBorder: {
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  label: {
    color: tokens.muted,
    flexShrink: 0,
  },
  value: {
    margin: 0,
    color: tokens.text,
    fontWeight: tokens.fontStrong,
    textAlign: "right",
    overflowWrap: "anywhere",
  },
  card: {
    padding: "5px 8px",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    backgroundColor: tokens.canvas,
    fontSize: "11.5px",
  },
  cardAlert: {
    backgroundColor: tokens.dangerSurface,
    borderColor: tokens.danger,
  },
  cardTitle: {
    display: "block",
    marginBottom: "2px",
    color: tokens.text,
  },
  cardTitleAlert: {
    color: tokens.danger,
  },
});
