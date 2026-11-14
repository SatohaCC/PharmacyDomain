import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { Badge } from "../data-display/badge";
import { Link } from "../navigation/link";
import { tokens } from "../theme/tokens.stylex";

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
      <header {...stylex.props(styles.header)}>
        <div {...stylex.props(styles.headerInner)}>
          <div {...stylex.props(styles.leftGroup)}>
            <div {...stylex.props(styles.brand)}>
              <Link href="/">{storeName || "調剤現場業務"}</Link>
            </div>
            <nav aria-label="業務メニュー" {...stylex.props(styles.navigation)}>
              {navigation}
            </nav>
          </div>
          <div {...stylex.props(styles.rightGroup)}>
            <Badge>{identity}</Badge>
          </div>
        </div>
      </header>
      <main {...stylex.props(styles.main)}>{children}</main>
    </div>
  );
}

const styles = stylex.create({
  shell: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100dvh",
  },
  header: {
    position: "sticky",
    top: 0,
    zIndex: 40,
    backgroundColor: tokens.surface,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
    boxShadow: tokens.shadow,
  },
  headerInner: {
    maxWidth: "1920px",
    width: "100%",
    marginInline: "auto",
    minHeight: "34px",
    paddingBlock: "2px",
    paddingInline: "10px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "6px",
    flexWrap: "wrap",
  },
  leftGroup: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
    minWidth: 0,
  },
  rightGroup: {
    display: "flex",
    alignItems: "center",
    gap: tokens.spaceXs,
    flexShrink: 0,
  },
  brand: {
    fontSize: "14px",
    fontWeight: tokens.fontStrong,
    lineHeight: "1.2",
    letterSpacing: "-0.01em",
    color: tokens.text,
    textDecoration: "none",
    whiteSpace: "nowrap",
  },
  navigation: {
    display: "flex",
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "2px",
    fontSize: "12px",
  },
  main: {
    maxWidth: "1920px",
    width: "100%",
    minWidth: 0,
    marginInline: "auto",
    paddingBlock: "6px",
    paddingInline: "10px",
    paddingBottom: "48px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
});
