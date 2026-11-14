import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";

export interface DetailFooterItem {
  id: string;
  label: string;
}

export interface DetailFooterBarProps {
  items: readonly DetailFooterItem[];
  activeId: string;
  onSelect: (id: string) => void;
}

/** 患者詳細画面の中央ペインを切り替えるフッターナビゲーションバー。 */
export function DetailFooterBar({
  items,
  activeId,
  onSelect,
}: DetailFooterBarProps) {
  return (
    <nav aria-label="患者詳細業務メニュー" {...stylex.props(styles.bar)}>
      {items.map((item) => {
        const isActive = item.id === activeId;
        return (
          <button
            key={item.id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(item.id)}
            {...stylex.props(styles.item, isActive && styles.activeItem)}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}

const styles = stylex.create({
  bar: {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: "4px",
    padding: "4px 6px",
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.panelRadius,
    boxShadow: tokens.shadowMd,
    pointerEvents: "auto",
  },
  item: {
    appearance: "none",
    cursor: "pointer",
    minBlockSize: "26px",
    paddingBlock: "3px",
    paddingInline: "10px",
    borderRadius: tokens.radius,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    backgroundColor: {
      default: tokens.canvas,
      ":hover:not([aria-pressed='true'])": tokens.surfaceSubtle,
    },
    color: tokens.text,
    fontSize: "11.5px",
    fontWeight: tokens.fontStrong,
    transition: "background-color 150ms ease, border-color 150ms ease, color 150ms ease",
    outline: { default: "none", ":focus-visible": `3px solid ${tokens.focus}` },
    outlineOffset: "2px",
  },
  activeItem: {
    backgroundColor: tokens.action,
    borderColor: tokens.action,
    color: tokens.onAction,
  },
});
