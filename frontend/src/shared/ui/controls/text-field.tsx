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
      <Label {...stylex.props(styles.label)}>
        {label}
        {required && <span {...stylex.props(styles.required)}>必須</span>}
      </Label>
      <Input {...stylex.props(styles.input)} />
      {description && (
        <Text slot="description" {...stylex.props(styles.description)}>
          {description}
        </Text>
      )}
      <FieldError {...stylex.props(styles.error)}>
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
  label: {
    fontSize: tokens.fontSm,
    fontWeight: tokens.fontStrong,
    color: tokens.text,
  },
  required: {
    fontSize: tokens.fontSm,
    marginLeft: tokens.spaceXs,
    color: tokens.danger,
  },
  input: {
    width: "100%",
    minWidth: 0,
    minHeight: "44px",
    fontSize: "max(1rem, 1em)",
    paddingBlock: "10px",
    paddingInline: tokens.spaceSm,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: {
      default: tokens.border,
      ":hover": tokens.muted,
      ":user-invalid": tokens.danger,
    },
    borderRadius: tokens.radius,
    backgroundColor: tokens.surface,
    color: tokens.text,
    transition: "border-color 150ms ease",
    outline: {
      default: "none",
      ":focus-visible": `2px solid ${tokens.action}`,
    },
    outlineOffset: "2px",
  },
  description: {
    fontSize: tokens.fontSm,
    color: tokens.muted,
  },
  error: {
    fontSize: tokens.fontSm,
    color: tokens.danger,
    fontWeight: tokens.fontStrong,
  },
});
