import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./ThreePane.styles";

export interface ThreePaneProps {
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  footer?: ReactNode;
}

/** 3カラム業務レイアウト（左・中央・右の3ペインと任意のフッター）。 */
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
