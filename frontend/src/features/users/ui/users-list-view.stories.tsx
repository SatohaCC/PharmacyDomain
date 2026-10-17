import type { Meta, StoryObj } from "@storybook/react-vite";
import { UserListView } from "./users-list-view";
const meta = {
  title: "画面/ユーザー一覧",
  component: UserListView,
  args: { corporateId: "example", data: { items: [], next_cursor: null } },
} satisfies Meta<typeof UserListView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 空: Story = {};
export const 一覧: Story = {
  args: {
    data: {
      items: [
        {
          id: "example-user",
          person_id: "example-person",
          role: "corporate_admin",
          status: "active",
          account_status: "active",
        },
      ],
      next_cursor: null,
    },
  },
};
