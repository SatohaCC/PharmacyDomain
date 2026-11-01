import type { Meta, StoryObj } from "@storybook/react-vite";
import { StoreListView } from "./stores-list-view";
const meta = {
  title: "画面/店舗一覧",
  component: StoreListView,
  args: { corporateId: "example", data: [] },
} satisfies Meta<typeof StoreListView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 空: Story = {};
export const 一覧: Story = {
  args: {
    data: [
      {
        id: "example-store",
        name: "テスト薬局",
        name_kana: "テストヤッキョク",
        code: "STR-001",
        status: "active",
        is_community_linkage: true,
        is_health_support: true,
      },
    ],
  },
};
