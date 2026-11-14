import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./Timeline.styles";

/** 縦一列の時系列タイムラインコンテナ。 */
export function TimelineList({ children }: { children: ReactNode }) {
  return <ol {...stylex.props(styles.list)}>{children}</ol>;
}

export interface TimelineSection {
  title: string;
  content: ReactNode;
}

export interface TimelineItemProps {
  dateLabel: string;
  stepLabel: string;
  selected?: boolean;
  isLatest?: boolean;
  isLast?: boolean;
  badges?: ReactNode;
  subtitle?: string;
  headerActions?: ReactNode;
  sections: readonly TimelineSection[];
}

/** タイムライン上の1ノード。左軸に日付と連続線、右カードにセクション一覧を表示する。 */
export function TimelineItem({
  dateLabel,
  stepLabel,
  selected = false,
  isLatest = false,
  isLast = false,
  badges,
  subtitle,
  headerActions,
  sections,
}: TimelineItemProps) {
  return (
    <li {...stylex.props(styles.item)}>
      <div {...stylex.props(styles.rail)}>
        <div {...stylex.props(styles.railMeta)}>
          <strong {...stylex.props(styles.dateText)}>{dateLabel}</strong>
          <span
            {...stylex.props(
              styles.stepText,
              (isLatest || selected) && styles.stepTextActive,
            )}
          >
            {stepLabel}
          </span>
        </div>
        <div {...stylex.props(styles.track)}>
          <span
            aria-hidden="true"
            {...stylex.props(
              styles.dot,
              (isLatest || selected) && styles.dotActive,
            )}
          />
          {!isLast ? (
            <span aria-hidden="true" {...stylex.props(styles.line)} />
          ) : null}
        </div>
      </div>

      <article
        {...stylex.props(styles.card, selected && styles.cardSelected)}
      >
        <header
          {...stylex.props(
            styles.cardHeader,
            selected && styles.cardHeaderSelected,
          )}
        >
          <div {...stylex.props(styles.headerLeft)}>
            {badges ? (
              <div {...stylex.props(styles.badgeRow)}>{badges}</div>
            ) : null}
            {subtitle ? (
              <div {...stylex.props(styles.institutionText)}>{subtitle}</div>
            ) : null}
          </div>
          {headerActions ? (
            <div {...stylex.props(styles.headerActions)}>{headerActions}</div>
          ) : null}
        </header>

        <div {...stylex.props(styles.cardBody)}>
          {sections.map((section) => (
            <section key={section.title} {...stylex.props(styles.sectionBlock)}>
              <h3 {...stylex.props(styles.blockTitle)}>{section.title}</h3>
              <div {...stylex.props(styles.blockContent)}>{section.content}</div>
            </section>
          ))}
        </div>
      </article>
    </li>
  );
}
