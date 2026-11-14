import type { Meta, StoryObj } from "@storybook/react-vite";
import { AdminFrame } from "./AdminFrame";
import { Heading, Paragraph } from "../../ui/Elements";
import { Panel } from "../../ui/Panel";
import { Link } from "../../ui/Link";
import { ActionCard } from "../ActionCard";

const meta = {
  title: "共通UI/レイアウト/管理画面",
  component: AdminFrame,
  parameters: { standalone: true },
  args: {
    brandHref: "/admin",
    brandLabel: "薬局管理",
    menuLabel: "管理メニュー",
    footnote: "操作範囲はログイン権限に従います",
    eyebrow: "ADMIN CONSOLE",
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
