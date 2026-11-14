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
export const Badge = element("span", "badge");
const styles = stylex.create({
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
