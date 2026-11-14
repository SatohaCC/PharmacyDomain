import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";

export interface ThreePaneProps {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  footer?: ReactNode;
}

/** 患者詳細などの3カラム業務レイアウト（左:患者情報 / 中:履歴・比較 / 右:今回記録）。 */
export function ThreePane({ left, center, right, footer }: ThreePaneProps) {
  return (
    <div {...stylex.props(styles.wrapper)}>
      <div {...stylex.props(styles.grid)}>
        <div {...stylex.props(styles.column)}>{left}</div>
        <div {...stylex.props(styles.column)}>{center}</div>
        <div {...stylex.props(styles.column, styles.stickyColumn)}>{right}</div>
      </div>
      {footer ? <div {...stylex.props(styles.footer)}>{footer}</div> : null}
    </div>
  );
}

const styles = stylex.create({
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceSm,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: {
      default: "minmax(250px, 280px) minmax(540px, 1fr) minmax(360px, 430px)",
      "@media (max-width: 1280px)": "1fr",
    },
    gap: tokens.spaceMd,
    alignItems: "start",
  },
  column: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceSm,
  },
  stickyColumn: {
    position: { default: "sticky", "@media (max-width: 1280px)": "static" },
    top: { default: "16px", "@media (max-width: 1280px)": "auto" },
    maxHeight: {
      default: "calc(100dvh - 104px)",
      "@media (max-width: 1280px)": "none",
    },
    overflowY: { default: "auto", "@media (max-width: 1280px)": "visible" },
    overscrollBehavior: "contain",
    scrollbarGutter: "stable",
  },
  footer: {
    position: "sticky",
    bottom: "12px",
    zIndex: 10,
    marginTop: tokens.spaceXs,
  },
});
