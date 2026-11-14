import * as stylex from "@stylexjs/stylex";
import { Link } from "../../ui/Link";
import { styles } from "./ActionCard.styles";

export function ActionCard({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <div {...stylex.props(styles.card)}>
      <Link href={href}>
        <strong>{title}</strong>
        <span {...stylex.props(styles.description)}>{description}</span>
      </Link>
    </div>
  );
}
