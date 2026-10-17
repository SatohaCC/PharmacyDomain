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
    fontSize: tokens.fontSm,
    backgroundColor: tokens.canvas,
    borderRadius: tokens.radius,
    paddingBlock: tokens.spaceXs,
    paddingInline: tokens.spaceSm,
  },
});
