import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { Button as AriaButton } from "react-aria-components";
import { styles } from "./Button.styles";

export interface ButtonProps {
  children: ReactNode;
  onAction?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  pending?: boolean;
  variant?: "primary" | "secondary";
  size?: "default" | "compact";
  "aria-label"?: string;
}
export function Button({
  children,
  onAction,
  type = "button",
  disabled,
  pending,
  variant = "primary",
  size = "default",
  "aria-label": ariaLabel,
}: ButtonProps) {
  return (
    <AriaButton
      {...stylex.props(
        styles.base,
        size === "compact" && styles.compact,
        variant === "secondary" && styles.secondary,
      )}
      type={type}
      aria-label={ariaLabel}
      isDisabled={disabled || pending}
      isPending={pending}
      onPress={onAction}
    >
      {children}
    </AriaButton>
  );
}
