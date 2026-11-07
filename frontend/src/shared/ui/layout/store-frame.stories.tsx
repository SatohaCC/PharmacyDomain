import type { Meta, StoryObj } from "@storybook/react-vite";
import { StoreFrame } from "./store-frame";
import { Link } from "../navigation/link";
import { Button } from "../controls/button";

const meta = {
  title: "共通UI/レイアウト/店舗業務画面",
  component: StoreFrame,
  parameters: {
    standalone: true,
  },
} satisfies Meta<typeof StoreFrame>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    storeName: "中央薬局 本店",
    identity: "店舗スタッフ (薬剤師)",
    navigation: (
      <>
        <Link href="#">患者一覧</Link>
        <Link href="#">新規患者登録</Link>
        <Link href="#">管理画面へ</Link>
        <Button variant="secondary" onAction={() => {}}>
          ログアウト
        </Button>
      </>
    ),
    children: (
      <div>
        <h2>患者業務ホーム</h2>
        <p>店舗コンテキストが適用された現場向け画面です。</p>
      </div>
    ),
  },
};
