import * as stylex from "@stylexjs/stylex";
import { tokens } from "../theme/tokens.stylex";
import { Link } from "./link";
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
const styles = stylex.create({
  card: {
    borderWidth: tokens.borderWidth,
    borderStyle: "solid",
    borderColor: tokens.border,
    borderRadius: tokens.radius,
    padding: tokens.spaceMd,
  },
  description: {
    display: "block",
    color: tokens.muted,
    fontSize: tokens.fontSm,
    marginTop: tokens.spaceXs,
  },
});
