import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";

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
        <div {...stylex.props(styles.column)}>{right}</div>
      </div>
      {footer ? <div {...stylex.props(styles.footer)}>{footer}</div> : null}
    </div>
  );
}

const styles = stylex.create({
  wrapper: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    width: "100%",
  },
  grid: {
    display: "grid",
    width: "100%",
    gridTemplateColumns: {
      default: "minmax(220px, 0.9fr) minmax(0, 3.2fr) minmax(260px, 1.9fr)",
      "@media (max-width: 1280px)": "1fr",
    },
    gap: "8px",
    alignItems: "start",
  },
  column: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  footer: {
    position: "fixed",
    bottom: "6px",
    left: 0,
    right: 0,
    zIndex: 30,
    display: "flex",
    justifyContent: "center",
    paddingInline: "8px",
    pointerEvents: "none",
  },
});
