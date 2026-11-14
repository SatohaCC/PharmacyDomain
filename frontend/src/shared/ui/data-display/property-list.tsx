import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";

/** 左ペイン向けのコンパクトなキー・バリュー一覧。 */
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

const styles = stylex.create({
  list: {
    margin: 0,
    display: "flex",
    flexDirection: "column",
  },
  row: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: tokens.spaceXs,
    paddingBlock: "3px",
    fontSize: "12px",
  },
  rowBorder: {
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  label: {
    color: tokens.muted,
    flexShrink: 0,
  },
  value: {
    margin: 0,
    color: tokens.text,
    fontWeight: tokens.fontStrong,
    textAlign: "right",
    overflowWrap: "anywhere",
  },
  card: {
    padding: "5px 8px",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    backgroundColor: tokens.canvas,
    fontSize: "11.5px",
  },
  cardAlert: {
    backgroundColor: tokens.dangerSurface,
    borderColor: tokens.danger,
  },
  cardTitle: {
    display: "block",
    marginBottom: "2px",
    color: tokens.text,
  },
  cardTitleAlert: {
    color: tokens.danger,
  },
});
