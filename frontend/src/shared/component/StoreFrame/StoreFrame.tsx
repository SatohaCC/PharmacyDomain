import type { ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { Badge } from "../../ui/Badge";
import { Link, NavScopeProvider } from "../../ui/Link";
import { styles } from "./StoreFrame.styles";

export interface StoreFrameProps {
  brandHref: string;
  brandLabel: ReactNode;
  navigationLabel: string;
  navigation: ReactNode;
  identity: ReactNode;
  children: ReactNode;
}

export function StoreFrame({
  brandHref,
  brandLabel,
  navigationLabel,
  navigation,
  identity,
  children,
}: StoreFrameProps) {
  return (
    <div {...stylex.props(styles.shell)}>
      <header {...stylex.props(styles.header)}>
        <div {...stylex.props(styles.headerInner)}>
          <div {...stylex.props(styles.leftGroup)}>
            <div {...stylex.props(styles.brand)}>
              <Link href={brandHref}>{brandLabel}</Link>
            </div>
            <nav
              aria-label={navigationLabel}
              {...stylex.props(styles.navigation)}
            >
              <NavScopeProvider>{navigation}</NavScopeProvider>
            </nav>
          </div>
          <div {...stylex.props(styles.rightGroup)}>
            <Badge>{identity}</Badge>
          </div>
        </div>
      </header>
      <main {...stylex.props(styles.main)}>{children}</main>
    </div>
  );
}
