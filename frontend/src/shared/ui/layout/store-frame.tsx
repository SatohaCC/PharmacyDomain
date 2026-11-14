import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { Badge } from "../data-display/badge";
import { Link } from "../navigation/link";
import { tokens } from "../theme/tokens.stylex";
import { Page, Eyebrow } from "./elements";

export interface StoreFrameProps {
  storeName?: string;
  navigation: ReactNode;
  identity: ReactNode;
  children: ReactNode;
}

export function StoreFrame({
  storeName,
  navigation,
  identity,
  children,
}: StoreFrameProps) {
  return (
    <div {...stylex.props(styles.shell)}>
      <aside {...stylex.props(styles.aside)}>
        <div {...stylex.props(styles.brand)}>
          <Link href="/">{storeName || "調剤現場業務"}</Link>
        </div>
        <details {...stylex.props(styles.menu)} open>
          <summary {...stylex.props(styles.menuSummary)}>業務メニュー</summary>
          <nav aria-label="業務メニュー" {...stylex.props(styles.navigation)}>
            {navigation}
          </nav>
        </details>
        <small {...stylex.props(styles.footnote)}>
          操作範囲はログイン権限と店舗コンテキストに従います
        </small>
      </aside>
      <Page>
        <header {...stylex.props(styles.header)}>
          <Eyebrow>DISPENSARY WORKSPACE</Eyebrow>
          <Badge>{identity}</Badge>
        </header>
        {children}
      </Page>
    </div>
  );
}

const styles = stylex.create({
  shell: {
    display: "grid",
    gridTemplateColumns: {
      default: "216px minmax(0,1fr)",
      "@media (max-width: 900px)": "1fr",
    },
    minHeight: "100dvh",
  },
  aside: {
    backgroundColor: tokens.surface,
    padding: tokens.spaceSm,
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceSm,
    position: { default: "sticky", "@media (max-width: 900px)": "static" },
    top: 0,
    alignSelf: "start",
    height: { default: "100dvh", "@media (max-width: 900px)": "auto" },
    overflowY: { default: "auto", "@media (max-width: 900px)": "visible" },
    borderInlineEndWidth: tokens.borderWidth,
    borderInlineEndStyle: "solid",
    borderInlineEndColor: tokens.border,
  },
  brand: {
    fontSize: "20px",
    fontWeight: tokens.fontStrong,
    letterSpacing: "-0.01em",
    color: tokens.text,
    textDecoration: "none",
    overflowWrap: "anywhere",
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
    fontSize: tokens.fontSm,
    lineHeight: "1.5",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: tokens.spaceSm,
    paddingBottom: tokens.spaceSm,
    marginBottom: tokens.spaceSm,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
});
