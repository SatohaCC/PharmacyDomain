import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { LoginView } from "./login-view";
const meta = {
  title: "画面/ログイン",
  component: LoginView,
  parameters: { standalone: true },
  args: {
    loginSubmission: { submit: fn(), pending: false, blocked: false },
    tokenSubmission: { submit: fn(), pending: false, blocked: false },
    passwordChangeRequired: false,
    authenticated: false,
  },
} satisfies Meta<typeof LoginView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {};
export const 初回パスワード変更: Story = {
  args: { passwordChangeRequired: true },
};
