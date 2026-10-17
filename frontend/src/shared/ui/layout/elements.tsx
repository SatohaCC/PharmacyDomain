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
export const Cards = element("div", "cards");
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
        <small>操作範囲はログイン権限に従います</small>
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
    minHeight: "100vh",
    fontFamily: '"Noto Sans JP", system-ui, sans-serif',
    fontSize: tokens.fontBody,
    lineHeight: tokens.lineHeight,
    color: tokens.text,
    backgroundColor: tokens.canvas,
  },
  page: {
    paddingBlock: tokens.spaceLg,
    paddingInline: {
      default: tokens.spaceLg,
      "@media (max-width: 750px)": tokens.spaceSm,
    },
    maxWidth: tokens.pageWidth,
    width: "100%",
    minWidth: 0,
    marginInline: "auto",
  },
  entry: {
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
    padding: {
      default: tokens.spaceLg,
      "@media (max-width: 750px)": tokens.spaceMd,
    },
  },
  heading: {
    fontSize: tokens.fontHeading,
    fontWeight: tokens.fontStrong,
    lineHeight: "1.4",
    marginTop: 0,
    marginBottom: tokens.spaceSm,
  },
  subheading: {
    fontSize: "21px",
    fontWeight: tokens.fontStrong,
    marginTop: 0,
    marginBottom: tokens.spaceMd,
  },
  sectionHeading: {
    fontSize: "17px",
    marginTop: tokens.spaceLg,
    marginBottom: tokens.spaceSm,
  },
  paragraph: {
    color: tokens.muted,
    marginBlock: tokens.spaceSm,
    overflowWrap: "anywhere",
  },
  title: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: tokens.spaceMd,
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
  cards: {
    display: "grid",
    gridTemplateColumns: {
      default: "1fr 1fr",
      "@media (max-width: 750px)": "1fr",
    },
    gap: tokens.spaceMd,
  },
  eyebrow: {
    fontSize: tokens.fontSm,
    letterSpacing: "0.12em",
    color: tokens.muted,
  },

  field: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceXs,
    marginBottom: tokens.spaceMd,
    maxWidth: tokens.formWidth,
  },
  input: {
    width: "100%",
    minWidth: 0,
    padding: "12px",
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
  details: { marginBlock: tokens.spaceMd },
  summary: { cursor: "pointer", marginBottom: tokens.spaceSm },
  shell: {
    display: "grid",
    gridTemplateColumns: {
      default: "230px minmax(0,1fr)",
      "@media (max-width: 750px)": "1fr",
    },
    minHeight: "100vh",
  },
  aside: {
    backgroundColor: tokens.surface,
    padding: tokens.spaceMd,
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceLg,
    borderInlineEndWidth: tokens.borderWidth,
    borderInlineEndStyle: "solid",
    borderInlineEndColor: tokens.border,
  },
  brand: {
    fontSize: "23px",
    fontWeight: tokens.fontStrong,
    color: tokens.text,
    textDecoration: "none",
  },
  menu: { margin: 0 },
  menuSummary: { cursor: "pointer", marginBottom: tokens.spaceSm },
  navigation: { display: "flex", flexDirection: "column", gap: tokens.spaceMd },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: tokens.spaceSm,
    paddingBottom: tokens.spaceMd,
    marginBottom: tokens.spaceLg,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
});
