import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { StoreRegistrationView } from "./stores-registration-view";
const meta = {
  title: "画面/店舗登録",
  component: StoreRegistrationView,
  args: { onSubmit: { submit: fn(), pending: false, blocked: false } },
} satisfies Meta<typeof StoreRegistrationView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {};
export const 処理中: Story = {
  args: { onSubmit: { submit: fn(), pending: true, blocked: false } },
};
export const 登録失敗: Story = {
  args: {
    onSubmit: {
      submit: fn(),
      pending: false,
      blocked: false,
      error: "入力内容を確認してください。",
    },
  },
};
