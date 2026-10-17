import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { CorporateListView } from "./corporates-list-view";
const meta = {
  title: "画面/法人一覧",
  component: CorporateListView,
  args: {
    data: { items: [], next_cursor: null },
    search: {},
    onSearch: { submit: fn(), pending: false, blocked: false },
  },
} satisfies Meta<typeof CorporateListView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 空: Story = {};
export const 一覧: Story = {
  args: {
    data: {
      items: [
        {
          id: "example",
          name: "テスト薬局グループ",
          representative_name: "テスト 太郎",
          is_active: true,
        },
      ],
      next_cursor: null,
    },
  },
};
