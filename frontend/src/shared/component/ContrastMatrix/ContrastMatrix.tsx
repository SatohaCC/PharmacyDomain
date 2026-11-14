import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./ContrastMatrix.styles";

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

export function ContrastEmptySlotHeader({
  label,
  subLabel,
}: {
  label: string;
  subLabel: ReactNode;
}) {
  return (
    <div {...stylex.props(styles.headerCell, styles.emptySlot)}>
      <span {...stylex.props(styles.emptySlotTitle)}>{label}</span>
      <span {...stylex.props(styles.emptySlotSub)}>{subLabel}</span>
    </div>
  );
}

export function ContrastEmptySlotCell({ children }: { children: ReactNode }) {
  return (
    <div {...stylex.props(styles.cell, styles.emptySlot)}>
      <span {...stylex.props(styles.emptySlotSub)}>{children}</span>
    </div>
  );
}
