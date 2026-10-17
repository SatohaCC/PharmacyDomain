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
    borderCollapse: "collapse",
    width: "100%",
    textAlign: "left",
    marginTop: tokens.spaceMd,
  },
  th: {
    color: tokens.muted,
    fontSize: tokens.fontSm,
    backgroundColor: tokens.canvas,
    fontWeight: tokens.fontStrong,
    padding: tokens.spaceSm,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  td: {
    padding: tokens.spaceSm,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  identifier: {
    fontSize: tokens.fontSm,
    overflowWrap: "anywhere",
    padding: tokens.spaceSm,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
});
