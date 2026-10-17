import {
  Button,
  FieldError,
  Label,
  ListBox,
  ListBoxItem,
  Popover,
  Select,
  SelectValue,
} from "react-aria-components";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
export interface SelectFieldProps {
  label: string;
  name?: string;
  value?: string;
  defaultValue?: string;
  required?: boolean;
  disabled?: boolean;
  options: readonly { value: string; label: string }[];
  onValueChange?: (value: string) => void;
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
}: SelectFieldProps) {
  return (
    <Select
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
      <Label>{label}{required && <span {...stylex.props(styles.required)}>必須</span>}</Label>
      <Button aria-label={label} {...stylex.props(styles.trigger)}>
        <SelectValue>
          {({ selectedText }) =>
            selectedText ||
            options.find((o) => o.value === "")?.label ||
            "選択してください"
          }
        </SelectValue>
        <span aria-hidden="true"> ▾</span>
      </Button>
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
      <FieldError>{label}を選択してください。</FieldError>
    </Select>
  );
}
const styles = stylex.create({
  required:{fontSize:tokens.fontSm,color:tokens.danger,marginLeft:tokens.spaceXs},
  field: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceXs,
    marginBottom: tokens.spaceMd,
    maxWidth: tokens.formWidth,
  },
  trigger: {
    display: "flex",
    justifyContent: "space-between",
    padding: "12px",
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    backgroundColor: tokens.surface,
    color: tokens.text,
    outline: {
      default: "none",
      ":focus-visible": `2px solid ${tokens.action}`,
    },
    outlineOffset: "2px",
    opacity: { default: 1, ":disabled": tokens.disabledOpacity },
  },
  popover: {
    backgroundColor: tokens.surface,
    color: tokens.text,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    minWidth: "var(--trigger-width)",
    boxShadow: tokens.shadow,
    maxHeight: "300px",
    overflowY: "auto",
  },
  list: { padding: tokens.spaceXs, outline: "none" },
  option: {
    paddingBlock: tokens.spaceXs,
    paddingInline: tokens.spaceSm,
    cursor: "pointer",
    borderRadius: tokens.radius,
    backgroundColor: {
      default: "transparent",
      ":is([data-focused])": tokens.canvas,
    },
    outline: {
      default: "none",
      ":is([data-focus-visible])": `2px solid ${tokens.action}`,
    },
  },
});
