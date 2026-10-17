import type { Meta, StoryObj } from "@storybook/react-vite";
import { AdminFrame, Heading, Paragraph } from "./elements";
import { Panel } from "./panel";
import { Link } from "../navigation/link";
import { ActionCard } from "../navigation/action-card";
const meta = {
  title: "共通UI/レイアウト/管理画面",
  component: AdminFrame,
  parameters: { standalone: true },
  args: {
    identity: "システム管理者",
    navigation: <Link href="/admin/corporates">法人管理</Link>,
    children: (
      <>
        <Heading>管理画面</Heading>
        <Paragraph>現在の操作範囲と、次の操作を確認します。</Paragraph>
        <Panel title="登録">
          <ActionCard
            href="/admin/corporates/new"
            title="法人を登録"
            description="法人の基本情報を入力します。"
          />
        </Panel>
      </>
    ),
  },
} satisfies Meta<typeof AdminFrame>;
export default meta;
export const 通常: StoryObj<typeof meta> = {};
