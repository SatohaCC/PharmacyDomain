import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";

/** 縦一列の時系列タイムラインコンテナ。 */
export function TimelineList({ children }: { children: ReactNode }) {
  return <ol {...stylex.props(styles.list)}>{children}</ol>;
}

export interface TimelineItemProps {
  dateLabel: string;
  stepLabel: string;
  selected?: boolean;
  isLatest?: boolean;
  isLast?: boolean;
  badges?: ReactNode;
  institutionText?: string;
  headerActions?: ReactNode;
  prescriptionContent: ReactNode;
  soapContent: ReactNode;
}

/** タイムライン上の1来局・1薬歴ノード。左軸に日付と連続線、右カードに処方・SOAPを並列表示する。 */
export function TimelineItem({
  dateLabel,
  stepLabel,
  selected = false,
  isLatest = false,
  isLast = false,
  badges,
  institutionText,
  headerActions,
  prescriptionContent,
  soapContent,
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
            {institutionText ? (
              <div {...stylex.props(styles.institutionText)}>
                {institutionText}
              </div>
            ) : null}
          </div>
          {headerActions ? (
            <div {...stylex.props(styles.headerActions)}>{headerActions}</div>
          ) : null}
        </header>

        <div {...stylex.props(styles.cardBody)}>
          <section {...stylex.props(styles.sectionBlock)}>
            <h3 {...stylex.props(styles.blockTitle)}>処方内容</h3>
            <div {...stylex.props(styles.blockContent)}>
              {prescriptionContent}
            </div>
          </section>
          <section {...stylex.props(styles.sectionBlock)}>
            <h3 {...stylex.props(styles.blockTitle)}>薬歴・指導要約（SOAP）</h3>
            <div {...stylex.props(styles.blockContent)}>{soapContent}</div>
          </section>
        </div>
      </article>
    </li>
  );
}

const styles = stylex.create({
  list: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column",
  },
  item: {
    display: "flex",
    gap: tokens.spaceSm,
    alignItems: "stretch",
    "@media (max-width: 750px)": {
      flexDirection: "column",
      gap: tokens.spaceXs,
      marginBottom: tokens.spaceSm,
    },
  },
  rail: {
    display: "flex",
    alignItems: "stretch",
    gap: "6px",
    width: "96px",
    flexShrink: 0,
    "@media (max-width: 750px)": {
      width: "auto",
    },
  },
  railMeta: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-end",
    textAlign: "right",
    width: "76px",
    paddingTop: "4px",
    "@media (max-width: 750px)": {
      flexDirection: "row",
      alignItems: "center",
      gap: tokens.spaceXs,
      textAlign: "left",
      width: "auto",
      paddingTop: 0,
    },
  },
  dateText: {
    fontSize: "11.5px",
    color: tokens.text,
    whiteSpace: "nowrap",
  },
  stepText: {
    fontSize: "10px",
    fontWeight: tokens.fontStrong,
    color: tokens.muted,
    marginTop: "1px",
  },
  stepTextActive: {
    color: tokens.action,
  },
  track: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    width: "14px",
    paddingTop: "8px",
    "@media (max-width: 750px)": {
      display: "none",
    },
  },
  dot: {
    width: "9px",
    height: "9px",
    borderRadius: "9999px",
    backgroundColor: tokens.surface,
    borderWidth: "2px",
    borderStyle: "solid",
    borderColor: tokens.border,
    flexShrink: 0,
  },
  dotActive: {
    backgroundColor: tokens.action,
    borderColor: tokens.action,
  },
  line: {
    width: "2px",
    flex: 1,
    minHeight: "12px",
    backgroundColor: tokens.border,
    marginTop: "3px",
  },
  card: {
    flex: 1,
    minWidth: 0,
    marginBottom: "6px",
    backgroundColor: tokens.surface,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    overflow: "hidden",
  },
  cardSelected: {
    borderColor: tokens.action,
    boxShadow: `0 0 0 1px ${tokens.action}`,
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "6px",
    padding: "4px 8px",
    backgroundColor: tokens.canvas,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  cardHeaderSelected: {
    backgroundColor: tokens.actionSubtle,
    borderBottomColor: tokens.action,
  },
  headerLeft: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    minWidth: 0,
  },
  badgeRow: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "4px",
  },
  institutionText: {
    fontSize: "11px",
    color: tokens.muted,
    overflowWrap: "anywhere",
  },
  headerActions: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    flexShrink: 0,
  },
  cardBody: {
    display: "grid",
    gridTemplateColumns: {
      default: "1fr 1fr",
      "@media (max-width: 900px)": "1fr",
    },
    gap: "6px",
    padding: "6px 8px",
  },
  sectionBlock: {
    minWidth: 0,
  },
  blockTitle: {
    margin: 0,
    marginBottom: "2px",
    fontSize: "11px",
    fontWeight: tokens.fontStrong,
    color: tokens.muted,
  },
  blockContent: {
    fontSize: "11.5px",
    color: tokens.text,
    lineHeight: "1.35",
    overflowWrap: "anywhere",
  },
});
