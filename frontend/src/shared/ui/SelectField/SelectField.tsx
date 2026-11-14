import * as stylex from "@stylexjs/stylex";
import {
  Button as AriaButton,
  FieldError,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select as AriaSelect,
  SelectValue,
} from "react-aria-components";
import { styles } from "./SelectField.styles";

export interface SelectFieldProps {
  label: string;
  name?: string;
  value?: string;
  defaultValue?: string;
  required?: boolean;
  disabled?: boolean;
  options: readonly { value: string; label: string }[];
  onValueChange?: (value: string) => void;
  requiredLabel?: string;
  placeholder?: string;
  requiredErrorMessage?: string;
}
export function SelectField({
  label,
  name,
  value,
  defaultValue,
  required,
  disabled,
  options,
  onValueChange,
  requiredLabel = "必須",
  placeholder = "選択してください",
  requiredErrorMessage,
}: SelectFieldProps) {
  return (
    <AriaSelect
      {...stylex.props(styles.field)}
      name={name}
      selectedKey={value === "" ? null : value}
      defaultSelectedKey={defaultValue || undefined}
      isRequired={required}
      isDisabled={disabled}
      onSelectionChange={(key) =>
        onValueChange?.(key === null ? "" : String(key))
      }
    >
      <Label {...stylex.props(styles.label)}>
        {label}
        {required && (
          <span {...stylex.props(styles.required)}>{requiredLabel}</span>
        )}
      </Label>
      <AriaButton aria-label={label} {...stylex.props(styles.trigger)}>
        <SelectValue>
          {({ selectedText }) =>
            selectedText ||
            options.find((o) => o.value === "")?.label ||
            placeholder
          }
        </SelectValue>
        <span aria-hidden="true"> ▾</span>
      </AriaButton>
      <Popover {...stylex.props(styles.popover)}>
        <ListBox {...stylex.props(styles.list)}>
          {options.map((o) => (
            <ListBoxItem
              {...stylex.props(styles.option)}
              id={o.value}
              key={o.value}
              textValue={o.label}
            >
              {o.label}
            </ListBoxItem>
          ))}
        </ListBox>
      </Popover>
      <FieldError {...stylex.props(styles.error)}>
        {requiredErrorMessage ?? `${label}を選択してください。`}
      </FieldError>
    </AriaSelect>
  );
}
