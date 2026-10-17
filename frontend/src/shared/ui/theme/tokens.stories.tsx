import type { Meta, StoryObj } from "@storybook/react-vite";
import * as stylex from "@stylexjs/stylex";
import { tokens } from "./tokens.stylex";
import { Heading, Subheading, Paragraph } from "../layout/elements";
import { Panel, Stack } from "../layout/panel";
function Tokens() {
  return (
    <Stack>
      <Heading>デザイントークン</Heading>
      <Panel title="色">
        <div {...stylex.props(styles.samples)}>
          <span {...stylex.props(styles.action)}>主要操作</span>
          <span {...stylex.props(styles.surface)}>標準の背景と文字</span>
          <span {...stylex.props(styles.error)}>エラー</span>
        </div>
      </Panel>
      <Panel title="文字">
        <Heading>ページ見出し</Heading>
        <Subheading>セクション見出し</Subheading>
        <Paragraph>
          本文は十分な行間で、長い日本語も読みやすく表示します。
        </Paragraph>
      </Panel>
      <Panel title="余白">
        <Stack gap="large">
          <Paragraph>大きな区切り</Paragraph>
          <Stack gap="small">
            <Paragraph>関連の強い項目</Paragraph>
            <Paragraph>関連の強い項目</Paragraph>
          </Stack>
        </Stack>
      </Panel>
    </Stack>
  );
}
const styles = stylex.create({
  samples: { display: "flex", flexWrap: "wrap", gap: tokens.spaceMd },
  action: {
    backgroundColor: tokens.action,
    color: tokens.onAction,
    padding: tokens.spaceMd,
  },
  surface: {
    backgroundColor: tokens.surface,
    color: tokens.text,
    padding: tokens.spaceMd,
  },
  error: {
    backgroundColor: tokens.dangerSurface,
    color: tokens.danger,
    padding: tokens.spaceMd,
  },
});
const meta = { title: "デザイン/トークン", component: Tokens } satisfies Meta<
  typeof Tokens
>;
export default meta;
export const 一覧: StoryObj<typeof meta> = {};
