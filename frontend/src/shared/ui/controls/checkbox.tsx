import { Checkbox as AriaCheckbox } from "react-aria-components";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
export function Checkbox({
  label,
  name,
  value,
  isSelected,
  defaultSelected,
  onChange,
  disabled,
  readOnly,
}: {
  label: string;
  name?: string;
  value?: string;
  isSelected?: boolean;
  defaultSelected?: boolean;
  onChange?: (isSelected: boolean) => void;
  disabled?: boolean;
  readOnly?: boolean;
}) {
  return (
    <AriaCheckbox
      {...stylex.props(styles.label)}
      name={name}
      value={value}
      isSelected={isSelected}
      defaultSelected={defaultSelected}
      onChange={onChange}
      isDisabled={disabled}
      isReadOnly={readOnly}
    >
      {({ isSelected: selected }) => (
        <>
          <span
            aria-hidden="true"
            {...stylex.props(styles.box, selected && styles.selected)}
          >
            {selected ? "✓" : ""}
          </span>
          {label}
        </>
      )}
    </AriaCheckbox>
  );
}
const styles = stylex.create({
  label: {
    display: "flex",
    gap: tokens.spaceXs,
    alignItems: "center",
    cursor: "pointer",
    outline: {
      default: "none",
      ":is([data-focus-visible])": `2px solid ${tokens.action}`,
    },
    outlineOffset: "2px",
  },
  box: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "22px",
    height: "22px",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: "4px",
    backgroundColor: tokens.surface,
  },
  selected: {
    backgroundColor: tokens.action,
    color: tokens.onAction,
    borderColor: tokens.action,
  },
});
