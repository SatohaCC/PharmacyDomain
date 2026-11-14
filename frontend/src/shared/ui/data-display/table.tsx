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
    marginTop: "6px",
    fontSize: "12px",
    fontVariantNumeric: "tabular-nums",
  },
  th: {
    color: tokens.muted,
    fontSize: "11.5px",
    backgroundColor: tokens.surfaceSubtle,
    fontWeight: tokens.fontStrong,
    whiteSpace: "nowrap",
    paddingBlock: "5px",
    paddingInline: "8px",
    borderTopWidth: tokens.borderWidth,
    borderTopStyle: "solid",
    borderTopColor: tokens.border,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  td: {
    paddingBlock: "6px",
    paddingInline: "8px",
    fontSize: "12px",
    verticalAlign: "middle",
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  identifier: {
    fontSize: "11.5px",
    overflowWrap: "anywhere",
    paddingBlock: "6px",
    paddingInline: "8px",
    verticalAlign: "middle",
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
});
