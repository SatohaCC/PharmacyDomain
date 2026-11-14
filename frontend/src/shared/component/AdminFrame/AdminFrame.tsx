import { useId, type ReactNode } from "react";
import * as stylex from "@stylexjs/stylex";
import { Badge } from "../../ui/Badge";
import { Eyebrow, Page } from "../../ui/Elements";
import { Link, NavScopeProvider } from "../../ui/Link";
import { styles } from "./AdminFrame.styles";

export interface AdminFrameProps {
  brandHref: string;
  brandLabel: ReactNode;
  menuLabel: string;
  footnote?: ReactNode;
  eyebrow?: ReactNode;
  navigation: ReactNode;
  identity: ReactNode;
  children: ReactNode;
}

export function AdminFrame({
  brandHref,
  brandLabel,
  menuLabel,
  footnote,
  eyebrow,
  navigation,
  identity,
  children,
}: AdminFrameProps) {
  const menuLabelId = useId();
  return (
    <div {...stylex.props(styles.shell)}>
      <aside {...stylex.props(styles.aside)}>
        <div {...stylex.props(styles.brand)}>
          <Link href={brandHref}>{brandLabel}</Link>
        </div>
        <div {...stylex.props(styles.menu)}>
          <p id={menuLabelId} {...stylex.props(styles.menuSummary)}>
            {menuLabel}
          </p>
          <nav
            aria-labelledby={menuLabelId}
            {...stylex.props(styles.navigation)}
          >
            <NavScopeProvider>{navigation}</NavScopeProvider>
          </nav>
        </div>
        {footnote ? (
          <small {...stylex.props(styles.footnote)}>{footnote}</small>
        ) : null}
      </aside>
      <Page>
        <header {...stylex.props(styles.header)}>
          {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : <span />}
          <Badge>{identity}</Badge>
        </header>
        {children}
      </Page>
    </div>
  );
}
