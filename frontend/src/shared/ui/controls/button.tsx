import { Button as AriaButton } from "react-aria-components";
import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
export interface ButtonProps {
  children: ReactNode;
  onAction?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  pending?: boolean;
  variant?: "primary" | "secondary";
}
export function Button({
  children,
  onAction,
  type = "button",
  disabled,
  pending,
  variant = "primary",
}: ButtonProps) {
  return (
    <AriaButton
      {...stylex.props(
        styles.base,
        variant === "secondary" && styles.secondary,
      )}
      type={type}
      isDisabled={disabled || pending}
      isPending={pending}
      onPress={onAction}
    >
      {children}
    </AriaButton>
  );
}
const styles = stylex.create({
  base: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: tokens.spaceXs,
    paddingBlock: "12px",
    paddingInline: tokens.spaceMd,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: "transparent",
    borderRadius: tokens.radius,
    fontWeight: tokens.fontStrong,
    cursor: { default: "pointer", ":disabled": "not-allowed" },
    color: tokens.onAction,
    backgroundColor: { default: tokens.action, ":hover": tokens.actionHover },
    outline: { default: "none", ":focus-visible": `3px solid ${tokens.focus}` },
    outlineOffset: "3px",
    opacity: { default: 1, ":disabled": tokens.disabledOpacity },
  },
  secondary: {
    color: tokens.action,
    borderColor: tokens.border,
    backgroundColor: { default: tokens.surface, ":hover": tokens.canvas },
  },
});
