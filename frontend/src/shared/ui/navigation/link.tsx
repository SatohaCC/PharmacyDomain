import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
import { createContext, useContext, type ReactNode } from "react";
const NavigationContext = createContext({
  navigate: (href: string) => location.assign(href),
  pathname: "",
});
export function NavigationProvider({
  navigate,
  pathname = "",
  children,
}: {
  navigate: (href: string) => void;
  pathname?: string;
  children: ReactNode;
}) {
  return (
    <NavigationContext.Provider value={{ navigate, pathname }}>
      {children}
    </NavigationContext.Provider>
  );
}
export function Link({
  href,
  children,
  appearance = "text",
}: {
  href: string;
  children: ReactNode;
  appearance?: "text" | "action";
}) {
  const { navigate, pathname } = useContext(NavigationContext);
  return (
    <a
      href={href}
      aria-current={
        pathname.replace(/\/$/, "") === href.replace(/\/$/, "")
          ? "page"
          : undefined
      }
      {...stylex.props(
        appearance === "action" ? styles.button : styles.link,
      )}
      onClick={(e) => {
        if (
          !e.defaultPrevented &&
          e.button === 0 &&
          !e.metaKey &&
          !e.ctrlKey &&
          !e.shiftKey &&
          !e.altKey
        ) {
          e.preventDefault();
          navigate(href);
        }
      }}
    >
      {children}
    </a>
  );
}

const styles = stylex.create({
  link: {
    display: "inline-flex",
    alignItems: "center",
    gap: tokens.spaceXs,
    minBlockSize: "26px",
    fontSize: "12px",
    color: tokens.action,
    textDecoration: { default: "none", ":hover": "underline" },
    backgroundColor: {
      default: "transparent",
      ":hover": tokens.surfaceSubtle,
      ":is([aria-current='page'])": tokens.actionSubtle,
    },
    fontWeight: {
      default: tokens.fontNormal,
      ":is([aria-current='page'])": tokens.fontStrong,
    },
    borderInlineStartWidth: "2px",
    borderInlineStartStyle: "solid",
    borderInlineStartColor: {
      default: "transparent",
      ":is([aria-current='page'])": tokens.action,
    },
    borderRadius: tokens.radius,
    paddingBlock: "2px",
    paddingInline: "8px",
    transition: "background-color 150ms ease, color 150ms ease, border-color 150ms ease",
    outline: { default: "none", ":focus-visible": `3px solid ${tokens.focus}` },
    outlineOffset: "2px",
    overflowWrap: "anywhere",
  },
  button: {
    display: "inline-flex",
    justifyContent: "center",
    alignItems: "center",
    width: "fit-content",
    minHeight: "28px",
    paddingBlock: "3px",
    paddingInline: "10px",
    borderRadius: tokens.radius,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    backgroundColor: {
      default: tokens.surface,
      ":hover": tokens.surfaceSubtle,
    },
    color: tokens.action,
    fontSize: "12px",
    lineHeight: "1.2",
    textDecoration: "none",
    fontWeight: tokens.fontStrong,
    whiteSpace: "nowrap",
    transition: "background-color 150ms ease, border-color 150ms ease",
    outline: { default: "none", ":focus-visible": `3px solid ${tokens.focus}` },
    outlineOffset: "3px",
  },
});
