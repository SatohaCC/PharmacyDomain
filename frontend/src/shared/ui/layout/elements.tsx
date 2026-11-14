import { Badge } from "../data-display/badge";
import { Link } from "../navigation/link";
import { createElement, type ComponentProps, type ReactNode } from "react";
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
export function AdminFrame({
  navigation,
  identity,
  children,
}: {
  navigation: ReactNode;
  identity: ReactNode;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(styles.shell)}>
      <aside {...stylex.props(styles.aside)}>
        <div {...stylex.props(styles.brand)}>
          <Link href="/admin">薬局管理</Link>
        </div>
        <details {...stylex.props(styles.menu)} open>
          <summary {...stylex.props(styles.menuSummary)}>管理メニュー</summary>
          <nav aria-label="管理メニュー" {...stylex.props(styles.navigation)}>
            {navigation}
          </nav>
        </details>
        <small {...stylex.props(styles.footnote)}>
          操作範囲はログイン権限に従います
        </small>
      </aside>
      <Page>
        <header {...stylex.props(styles.header)}>
          <Eyebrow>ADMIN CONSOLE</Eyebrow>
          <Badge>{identity}</Badge>
        </header>
        {children}
      </Page>
    </div>
  );
}
const styles = stylex.create({
  canvas: {
    minHeight: "100dvh",
    fontFamily: '"Noto Sans JP", system-ui, sans-serif',
    fontSize: tokens.fontBody,
    lineHeight: tokens.lineHeight,
    color: tokens.text,
    backgroundColor: tokens.canvas,
  },
  page: {
    paddingBlock: tokens.spaceSm,
    paddingInline: {
      default: tokens.spaceMd,
      "@media (max-width: 750px)": tokens.spaceSm,
    },
    maxWidth: tokens.pageWidth,
    width: "100%",
    minWidth: 0,
    marginInline: "auto",
  },
  entry: {
    width: "100%",
    maxWidth: tokens.formWidth,
    marginBlock: {
      default: tokens.spaceXl,
      "@media (max-width: 750px)": tokens.spaceMd,
    },
    marginInline: "auto",
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.panelRadius,
    boxShadow: tokens.shadowMd,
    padding: {
      default: tokens.spaceLg,
      "@media (max-width: 750px)": tokens.spaceMd,
    },
  },
  heading: {
    fontSize: tokens.fontHeading,
    fontWeight: tokens.fontStrong,
    letterSpacing: "-0.01em",
    lineHeight: "1.25",
    marginTop: 0,
    marginBottom: "6px",
  },
  subheading: {
    fontSize: "14px",
    fontWeight: tokens.fontStrong,
    lineHeight: "1.25",
    letterSpacing: "-0.01em",
    marginTop: 0,
    marginBottom: "4px",
  },
  sectionHeading: {
    fontSize: "13px",
    fontWeight: tokens.fontStrong,
    lineHeight: "1.25",
    marginTop: 0,
    marginBottom: "4px",
  },
  paragraph: {
    fontSize: "12px",
    lineHeight: "1.35",
    color: tokens.muted,
    marginBlock: "4px",
    overflowWrap: "anywhere",
  },
  title: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: tokens.spaceSm,
    flexWrap: "wrap",
  },
  row: {
    display: "grid",
    gridTemplateColumns: {
      default: "1fr 1fr",
      "@media (max-width: 750px)": "1fr",
    },
    gap: tokens.spaceMd,
    maxWidth: tokens.formWidth,
  },
  actionRow: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: tokens.spaceSm,
  },
  spreadRow: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: tokens.spaceSm,
    marginBlock: tokens.spaceSm,
  },
  comparisonGrid: {
    display: "grid",
    gridTemplateColumns: {
      default: "repeat(3, minmax(0, 1fr))",
      "@media (max-width: 1024px)": "1fr",
    },
    gap: tokens.spaceSm,
    marginTop: tokens.spaceSm,
  },
  cards: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
    gap: tokens.spaceMd,
  },
  card: {
    containerType: "inline-size",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: { default: tokens.border, ":hover": tokens.action },
    borderRadius: tokens.panelRadius,
    padding: "10px 12px",
    boxShadow: tokens.shadow,
    transition: "border-color 150ms ease, box-shadow 150ms ease",
  },
  metaText: {
    fontSize: tokens.fontSm,
    color: tokens.muted,
  },
  statValue: {
    fontSize: "20px",
    fontWeight: tokens.fontStrong,
    lineHeight: "1.2",
    color: tokens.text,
  },
  eyebrow: {
    fontSize: tokens.fontSm,
    letterSpacing: "0.12em",
    color: tokens.muted,
  },

  field: {
    display: "flex",
    flexDirection: "column",
    gap: "3px",
    marginBottom: "6px",
    maxWidth: tokens.formWidth,
  },
  input: {
    width: "100%",
    minWidth: 0,
    padding: "5px 8px",
    fontSize: "12px",
    lineHeight: "1.35",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    backgroundColor: tokens.surface,
    color: tokens.text,
    outline: {
      default: "none",
      ":focus-visible": `2px solid ${tokens.action}`,
    },
    outlineOffset: "2px",
  },

  check: { display: "flex", alignItems: "center", gap: tokens.spaceXs },
  notice: {
    padding: tokens.spaceSm,
    backgroundColor: tokens.canvas,
    borderInlineStartWidth: "3px",
    borderInlineStartStyle: "solid",
    borderInlineStartColor: tokens.action,
    borderRadius: tokens.radius,
    marginBlock: tokens.spaceMd,
  },
  details: { marginBlock: "6px" },
  summary: {
    cursor: "pointer",
    fontWeight: tokens.fontStrong,
    fontSize: "12px",
    color: tokens.action,
    paddingBlock: "2px",
    marginBottom: "4px",
  },
  shell: {
    display: "grid",
    gridTemplateColumns: {
      default: "256px minmax(0,1fr)",
      "@media (max-width: 750px)": "1fr",
    },
    minHeight: "100dvh",
  },
  aside: {
    backgroundColor: tokens.surface,
    padding: tokens.spaceMd,
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceMd,
    position: { default: "sticky", "@media (max-width: 750px)": "static" },
    top: 0,
    alignSelf: "start",
    height: { default: "100dvh", "@media (max-width: 750px)": "auto" },
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
    cursor: "pointer",
    fontSize: tokens.fontSm,
    fontWeight: tokens.fontStrong,
    color: tokens.muted,
    letterSpacing: "0.04em",
    marginBottom: tokens.spaceSm,
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
    paddingBottom: tokens.spaceMd,
    marginBottom: tokens.spaceMd,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
});
