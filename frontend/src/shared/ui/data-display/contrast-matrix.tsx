import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";

export function ContrastMatrixFrame({ children }: { children: ReactNode }) {
  return <div {...stylex.props(styles.frame)}>{children}</div>;
}

export function ContrastMatrixRow({
  children,
  bordered = false,
}: {
  children: ReactNode;
  bordered?: boolean;
}) {
  return (
    <div {...stylex.props(styles.grid, bordered && styles.rowBorder)}>
      {children}
    </div>
  );
}

export function ContrastHeaderCell({
  selected = false,
  children,
}: {
  selected?: boolean;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(styles.headerCell, selected && styles.headerSelected)}>
      {children}
    </div>
  );
}

export function ContrastSectionBar({ children }: { children: ReactNode }) {
  return <div {...stylex.props(styles.sectionBar)}>{children}</div>;
}

export function ContrastCell({
  selected = false,
  children,
}: {
  selected?: boolean;
  children: ReactNode;
}) {
  return (
    <div {...stylex.props(styles.cell, selected && styles.cellSelected)}>
      {children}
    </div>
  );
}

export function ContrastDiffText({ children }: { children: ReactNode }) {
  return <span {...stylex.props(styles.diffText)}>{children}</span>;
}

export type ContrastStatusTone =
  | "added"
  | "changed"
  | "discontinued"
  | "unchanged"
  | "slot";

export function ContrastStatusTag({
  tone,
  children,
}: {
  tone: ContrastStatusTone;
  children: ReactNode;
}) {
  return (
    <span {...stylex.props(styles.statusTag, styles[`tag_${tone}`])}>
      {children}
    </span>
  );
}

export function ContrastSummaryBanner({
  hasChanges,
  children,
}: {
  hasChanges: boolean;
  children: ReactNode;
}) {
  return (
    <div
      role="status"
      {...stylex.props(
        styles.summaryBanner,
        hasChanges ? styles.summaryChanged : styles.summaryDo,
      )}
    >
      {children}
    </div>
  );
}

export function ContrastEmptySlotHeader({ label }: { label: string }) {
  return (
    <div {...stylex.props(styles.headerCell, styles.emptySlot)}>
      <span {...stylex.props(styles.emptySlotTitle)}>{label}</span>
      <span {...stylex.props(styles.emptySlotSub)}>履歴なし</span>
    </div>
  );
}

export function ContrastEmptySlotCell() {
  return (
    <div {...stylex.props(styles.cell, styles.emptySlot)}>
      <span {...stylex.props(styles.emptySlotSub)}>—</span>
    </div>
  );
}

const styles = stylex.create({
  frame: {
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    overflow: "hidden",
    backgroundColor: tokens.surface,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: {
      default: "repeat(3, minmax(0, 1fr))",
      "@media (max-width: 900px)": "1fr",
    },
  },
  rowBorder: {
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
  },
  headerCell: {
    padding: "5px 8px",
    borderBottomWidth: "2px",
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
    borderInlineEndWidth: tokens.borderWidth,
    borderInlineEndStyle: "solid",
    borderInlineEndColor: tokens.border,
    backgroundColor: tokens.canvas,
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    minWidth: 0,
  },
  headerSelected: {
    backgroundColor: tokens.actionSubtle,
    borderBottomColor: tokens.action,
  },
  sectionBar: {
    padding: "2px 8px",
    backgroundColor: tokens.surfaceSubtle,
    borderBottomWidth: tokens.borderWidth,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.border,
    fontSize: "11px",
    fontWeight: tokens.fontStrong,
    color: tokens.text,
  },
  cell: {
    padding: "3px 8px",
    borderInlineEndWidth: tokens.borderWidth,
    borderInlineEndStyle: "solid",
    borderInlineEndColor: tokens.border,
    minWidth: 0,
  },
  cellSelected: {
    backgroundColor: tokens.actionSubtle,
  },
  diffText: {
    color: tokens.danger,
    fontWeight: tokens.fontStrong,
  },
  statusTag: {
    display: "inline-flex",
    alignItems: "center",
    paddingBlock: "0px",
    paddingInline: "5px",
    borderRadius: "9999px",
    fontSize: "10.5px",
    fontWeight: tokens.fontStrong,
    lineHeight: "1.4",
    whiteSpace: "nowrap",
  },
  tag_added: {
    backgroundColor: tokens.action,
    color: tokens.onAction,
  },
  tag_changed: {
    backgroundColor: tokens.dangerSurface,
    color: tokens.danger,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.danger,
  },
  tag_discontinued: {
    backgroundColor: tokens.dangerSurface,
    color: tokens.danger,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.danger,
  },
  tag_unchanged: {
    backgroundColor: tokens.surfaceSubtle,
    color: tokens.muted,
  },
  tag_slot: {
    backgroundColor: tokens.surfaceSubtle,
    color: tokens.text,
  },
  summaryBanner: {
    padding: "4px 8px",
    borderRadius: tokens.radius,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    fontSize: "11.5px",
    fontWeight: tokens.fontStrong,
    marginBottom: "4px",
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "6px",
  },
  summaryChanged: {
    backgroundColor: tokens.dangerSurface,
    borderColor: tokens.focus,
    color: tokens.text,
  },
  summaryDo: {
    backgroundColor: tokens.actionSubtle,
    borderColor: tokens.action,
    color: tokens.text,
  },
  emptySlot: {
    backgroundColor: tokens.canvas,
    opacity: 0.75,
  },
  emptySlotTitle: {
    fontSize: tokens.fontSm,
    fontWeight: tokens.fontStrong,
    color: tokens.muted,
  },
  emptySlotSub: {
    fontSize: "12px",
    color: tokens.muted,
  },
});
