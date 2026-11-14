import * as stylex from "@stylexjs/stylex";
import {Checkbox as AriaCheckbox} from "react-aria-components";
import {styles} from "./Checkbox.styles";

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
