import type { Meta, StoryObj } from "@storybook/react-vite";
import { Alert, EmptyState } from "./alert";
const meta = {
  title: "共通UI/通知",
  component: Alert,
  args: { children: "入力内容を確認してください。" },
} satisfies Meta<typeof Alert>;
export default meta;
type Story = StoryObj<typeof meta>;
export const エラー: Story = {};
export const 案内: Story = {
  args: { tone: "info", children: "処理中です。しばらくお待ちください。" },
};
export const 空: Story = { render: () => <EmptyState /> };
