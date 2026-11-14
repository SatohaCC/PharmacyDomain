import * as stylex from "@stylexjs/stylex";
import {
  FieldError,
  Input,
  Label,
  Text,
  TextField as AriaTextField,
} from "react-aria-components";
import { styles } from "./TextField.styles";

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
  requiredLabel?: string;
  requiredErrorMessage?: string;
  formatErrorMessage?: string;
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
  requiredLabel = "必須",
  requiredErrorMessage,
  formatErrorMessage = "入力形式を確認してください。",
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
        {required && (
          <span {...stylex.props(styles.required)}>{requiredLabel}</span>
        )}
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
            ? (requiredErrorMessage ?? `${label}を入力してください。`)
            : formatErrorMessage)
        }
      </FieldError>
    </AriaTextField>
  );
}
