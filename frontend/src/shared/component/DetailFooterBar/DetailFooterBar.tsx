import * as stylex from "@stylexjs/stylex";
import { styles } from "./DetailFooterBar.styles";

export interface DetailFooterItem {
  id: string;
  label: string;
}

export interface DetailFooterBarProps {
  ariaLabel: string;
  items: readonly DetailFooterItem[];
  activeId: string;
  onSelect: (id: string) => void;
}

/** 画面下部で表示モードを切り替えるフッターナビゲーションバー。 */
export function DetailFooterBar({
  ariaLabel,
  items,
  activeId,
  onSelect,
}: DetailFooterBarProps) {
  return (
    <nav aria-label={ariaLabel} {...stylex.props(styles.bar)}>
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
