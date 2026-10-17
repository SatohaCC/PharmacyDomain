import {
  TextField as AriaTextField,
  Label,
  Input,
  Text,
  FieldError,
} from "react-aria-components";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
export interface TextFieldProps {
  name: string;
  label: string;
  required?: boolean;
  type?: "text" | "email" | "password" | "date" | "datetime-local";
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  readOnly?: boolean;
  disabled?: boolean;
  description?: string;
  error?: string;
}
export function TextField({
  name,
  label,
  required,
  type = "text",
  defaultValue,
  value,
  onValueChange,
  readOnly,
  disabled,
  description,
  error,
}: TextFieldProps) {
  return (
    <AriaTextField
      {...stylex.props(styles.field)}
      name={name}
      type={type}
      isRequired={required}
      isReadOnly={readOnly}
      isDisabled={disabled}
      isInvalid={error ? true : undefined}
      defaultValue={defaultValue}
      value={value}
      onChange={onValueChange}
    >
      <Label>
        {label}
        {required && <span {...stylex.props(styles.required)}>必須</span>}
      </Label>
      <Input {...stylex.props(styles.input)} />
      {description && <Text slot="description">{description}</Text>}
      <FieldError>
        {({ validationDetails }) =>
          error ||
          (validationDetails.valueMissing
            ? `${label}を入力してください。`
            : "入力形式を確認してください。")
        }
      </FieldError>
    </AriaTextField>
  );
}
const styles = stylex.create({
  field: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spaceXs,
    marginBottom: tokens.spaceMd,
    maxWidth: tokens.formWidth,
  },
  required: {
    fontSize: tokens.fontSm,
    marginLeft: tokens.spaceXs,
    color: tokens.danger,
  },
  input: {
    width: "100%",
    minWidth: 0,
    paddingBlock: "12px",
    paddingInline: tokens.spaceSm,
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
  },
});
