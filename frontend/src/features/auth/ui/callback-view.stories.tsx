import type { Meta, StoryObj } from "@storybook/react-vite";
import { CallbackView } from "./callback-view";
const meta = {
  title: "画面/ログイン確認",
  component: CallbackView,
  parameters: { standalone: true },
} satisfies Meta<typeof CallbackView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 読込中: Story = {};
export const 失敗: Story = {
  args: { error: "本人確認できませんでした。再度ログインしてください。" },
};
