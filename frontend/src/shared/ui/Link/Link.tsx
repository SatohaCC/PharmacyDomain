import * as stylex from "@stylexjs/stylex";
import { createContext, useContext, type ReactNode } from "react";
import { styles } from "./Link.styles";

const NavigationContext = createContext({
  navigate: (href: string) => location.assign(href),
  pathname: "",
});
const NavScopeContext = createContext(false);

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

/** ナビゲーション領域内のリンクに現在ページ判定（aria-current="page"）を有効化する。 */
export function NavScopeProvider({ children }: { children: ReactNode }) {
  return (
    <NavScopeContext.Provider value={true}>{children}</NavScopeContext.Provider>
  );
}

export function Link({
  href,
  children,
  appearance = "text",
  ariaLabel,
  ariaDescribedBy,
}: {
  href: string;
  children: ReactNode;
  appearance?: "text" | "action" | "nav";
  ariaLabel?: string;
  ariaDescribedBy?: string;
}) {
  const { navigate, pathname } = useContext(NavigationContext);
  const inNavScope = useContext(NavScopeContext);
  const isNavLink =
    appearance === "nav" || (appearance === "text" && inNavScope);
  const isCurrent =
    isNavLink &&
    pathname.length > 0 &&
    pathname.replace(/\/$/, "") === href.replace(/\/$/, "");
  return (
    <a
      href={href}
      aria-current={isCurrent ? "page" : undefined}
      aria-label={ariaLabel}
      aria-describedby={ariaDescribedBy}
      {...stylex.props(
        appearance === "action"
          ? styles.button
          : isNavLink
            ? styles.navLink
            : styles.link,
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
