import { createElement, type ComponentProps, type ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./Elements.styles";

function element<Tag extends keyof React.JSX.IntrinsicElements>(
  tag: Tag,
  name: keyof typeof styles,
) {
  return function Element(props: ComponentProps<Tag>) {
    return createElement(tag, { ...props, ...stylex.props(styles[name]) });
  };
}
export const Page = element("main", "page");
export const Entry = element("main", "entry");
export const Heading = element("h1", "heading");
export const Subheading = element("h2", "subheading");
export const SectionHeading = element("h3", "sectionHeading");
export const Paragraph = element("p", "paragraph");
export const Title = element("div", "title");
export const Row = element("div", "row");
export const ActionRow = element("div", "actionRow");
export const SpreadRow = element("div", "spreadRow");
export const ComparisonGrid = element("div", "comparisonGrid");
export const Cards = element("div", "cards");
export const Card = element("article", "card");
export const MetaText = element("span", "metaText");
export const StatValue = element("strong", "statValue");
export const Eyebrow = element("span", "eyebrow");

export const FieldGroup = element("div", "field");
export const FieldLabel = element("label", "field");
export const TextArea = element("textarea", "input");

export const CheckLabel = element("label", "check");
export const Notice = element("p", "notice");
export const Details = element("details", "details");
export const Summary = element("summary", "summary");
export function Canvas({ children }: { children: ReactNode }) {
  return <div {...stylex.props(styles.canvas)}>{children}</div>;
}
