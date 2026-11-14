import { createElement, type ComponentProps } from "react";
import * as stylex from "@stylexjs/stylex";
import { styles } from "./Table.styles";

function element<Tag extends keyof React.JSX.IntrinsicElements>(
  tag: Tag,
  name: keyof typeof styles,
) {
  return function Element(props: ComponentProps<Tag>) {
    return createElement(tag, { ...props, ...stylex.props(styles[name]) });
  };
}
export interface TableProps extends ComponentProps<"table"> {
  ariaLabel?: string;
  ariaLabelledBy?: string;
}

/** 水平・垂直スクロールとコンテナ基準のレスポンシブ表示に対応するデータテーブル。 */
export function Table({
  ariaLabel,
  ariaLabelledBy,
  children,
  ...props
}: TableProps) {
  const hasLabel = Boolean(ariaLabel || ariaLabelledBy);
  return (
    <div
      tabIndex={hasLabel ? 0 : undefined}
      role={hasLabel ? "region" : undefined}
      aria-label={ariaLabel}
      aria-labelledby={ariaLabelledBy}
      {...stylex.props(styles.wrapper)}
    >
      <table {...props} {...stylex.props(styles.table)}>
        {children}
      </table>
    </div>
  );
}

/** 列見出しセル（デフォルト scope="col"）。 */
export function TableHeader({ scope = "col", ...props }: ComponentProps<"th">) {
  return <th scope={scope} {...props} {...stylex.props(styles.th)} />;
}

/** 行見出しセル（デフォルト scope="row"）。 */
export function TableRowHeader({
  scope = "row",
  ...props
}: ComponentProps<"th">) {
  return <th scope={scope} {...props} {...stylex.props(styles.rowHeader)} />;
}

export const TableCell = element("td", "td");
export const IdentifierCell = element("td", "identifier");
