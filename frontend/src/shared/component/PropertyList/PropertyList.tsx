import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./PropertyList.styles";

/** 狭いカラム向けのコンパクトなキー・バリュー一覧。 */
export function PropertyList({ children }: { children: ReactNode }) {
  return <dl {...stylex.props(styles.list)}>{children}</dl>;
}

export function PropertyRow({
  label,
  value,
  isLast = false,
}: {
  label: string;
  value: ReactNode;
  isLast?: boolean;
}) {
  return (
    <div {...stylex.props(styles.row, !isLast && styles.rowBorder)}>
      <dt {...stylex.props(styles.label)}>{label}</dt>
      <dd {...stylex.props(styles.value)}>{value}</dd>
    </div>
  );
}

/** 狭いカラム内で縦に並べるコンパクトな情報カード。 */
export function CompactInfoCard({
  title,
  tone = "default",
  children,
}: {
  title: string;
  tone?: "default" | "alert";
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(styles.card, tone === "alert" && styles.cardAlert)}>
      <strong
        {...stylex.props(
          styles.cardTitle,
          tone === "alert" && styles.cardTitleAlert,
        )}
      >
        {title}
      </strong>
      {children}
    </div>
  );
}
