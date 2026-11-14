import { createElement, type ComponentProps } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
function element<Tag extends keyof React.JSX.IntrinsicElements>(
  tag: Tag,
  name: keyof typeof styles,
) {
  return function Element(props: ComponentProps<Tag>) {
    return createElement(tag, { ...props, ...stylex.props(styles[name]) });
  };
}
export const Table = element("table", "table");
export const TableHeader = element("th", "th");
export const TableCell = element("td", "td");
export const IdentifierCell = element("td", "identifier");
const styles = stylex.create({
  table: {
    borderCollapse: "separate",
    borderSpacing: 0,
    width: "100%",
    textAlign: "left",
    marginTop: tokens.spaceMd,
    fontVariantNumeric: "tabular-nums",
  },
  th: {
    color: tokens.muted,
    fontSize: tokens.fontSm,
    backgroundColor: tokens.surfaceSubtle,
    fontWeight: tokens.fontStrong,
    whiteSpace: "nowrap",
    paddingBlock: "10px",
    paddingInline: tokens.spaceSm,
    borderTopWidth: tokens.borderWidth,
    borderTopStyle: "solid",
    borderTopColor: tokens.border,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  td: {
    paddingBlock: "12px",
    paddingInline: tokens.spaceSm,
    verticalAlign: "middle",
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  identifier: {
    fontSize: tokens.fontSm,
    overflowWrap: "anywhere",
    paddingBlock: "12px",
    paddingInline: tokens.spaceSm,
    verticalAlign: "middle",
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
});
