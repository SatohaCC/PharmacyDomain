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
      {...stylex.props(styles.link, appearance === "action" && styles.button)}
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
    color: tokens.action,
    textDecoration: { default: "none", ":hover": "underline" },
    outline: { default: "none", ":focus-visible": `3px solid ${tokens.focus}` },
    outlineOffset: "3px",
    overflowWrap: "anywhere",
  },
  button: {
    display: "inline-flex",
    justifyContent: "center",
    alignItems: "center",
    paddingBlock: "12px",
    paddingInline: tokens.spaceMd,
    borderRadius: tokens.radius,
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    backgroundColor: tokens.surface,
    fontWeight: tokens.fontStrong,
  },
});
