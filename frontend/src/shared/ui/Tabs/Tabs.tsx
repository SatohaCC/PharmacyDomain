import { createElement, type ComponentProps } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./Tabs.styles";

function element<Tag extends keyof React.JSX.IntrinsicElements>(
  tag: Tag,
  name: keyof typeof styles,
) {
  return function Element(props: ComponentProps<Tag>) {
    return createElement(tag, { ...props, ...stylex.props(styles[name]) });
  };
}
export const Tabs = element("nav", "tabs");
