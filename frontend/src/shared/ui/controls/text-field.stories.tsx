import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { TextField } from "./text-field";
const meta = {
  title: "共通UI/操作/入力",
  component: TextField,
  args: { name: "name", label: "法人名", required: true, onValueChange: fn() },
} satisfies Meta<typeof TextField>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {
  play: async ({ canvasElement, args }) => {
    await userEvent.type(
      within(canvasElement).getByLabelText(/法人名/),
      "テスト薬局",
    );
    await expect(args.onValueChange).toHaveBeenLastCalledWith("テスト薬局");
  },
};
export const 入力エラー: Story = {
  args: { value: "", error: "法人名を入力してください。" },
  play: async ({ canvasElement }) => {
    const field = within(canvasElement).getByLabelText(/法人名/);
    await expect(field).toHaveAttribute("aria-invalid", "true");
    await expect(field).toHaveAccessibleDescription(
      "法人名を入力してください。",
    );
  },
};
export const 長い日本語: Story = {
  args: {
    label: "法人を正式に識別するための名称を省略せずに入力してください",
    description: "登記上の名称を入力してください。",
    defaultValue: "一般社団法人テスト薬局グループ地域医療支援センター",
  },
};
