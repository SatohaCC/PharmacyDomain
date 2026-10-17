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
export const Tabs = element("nav", "tabs");
const styles = stylex.create({
  tabs: {
    display: "flex",
    gap: tokens.spaceMd,
    flexWrap: "wrap",
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
    paddingBlock: tokens.spaceMd,
  },
});
