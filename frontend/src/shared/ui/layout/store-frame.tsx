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
      default: "250px minmax(0,1fr)",
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
    fontSize: "20px",
    fontWeight: tokens.fontStrong,
    color: tokens.text,
    textDecoration: "none",
    overflowWrap: "anywhere",
  },
  menu: { margin: 0 },
  menuSummary: { cursor: "pointer", marginBottom: tokens.spaceSm },
  navigation: { display: "flex", flexDirection: "column", gap: tokens.spaceMd },
  footnote: {
    color: tokens.muted,
    fontSize: tokens.fontSm,
  },
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
