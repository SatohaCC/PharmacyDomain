import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, fireEvent, userEvent, within } from "storybook/test";
import { Form } from "./form";
import { TextField } from "./text-field";
const meta = {
  title: "共通UI/操作/フォーム",
  component: Form,
  args: { onSubmit: fn(), children: <TextField name="name" label="法人名" /> },
} satisfies Meta<typeof Form>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {};
export const 必須項目の入力エラー: Story = {
  args: { children: <TextField name="name" label="法人名" required /> },
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    await userEvent.click(c.getByRole("button", { name: "登録する" }));
    await expect(
      await c.findByText("法人名を入力してください。"),
    ).toBeVisible();
    await expect(c.getByLabelText(/法人名/)).toHaveFocus();
    await expect(args.onSubmit).not.toHaveBeenCalled();
  },
};
export const IME変換中は送信しない: Story = {
  play: async ({ canvasElement, args }) => {
    const input = within(canvasElement).getByLabelText("法人名");
    const allowed = fireEvent.keyDown(input, {
      key: "Enter",
      code: "Enter",
      isComposing: true,
      keyCode: 229,
    });
    await expect(allowed).toBe(false);
    await expect(args.onSubmit).not.toHaveBeenCalled();
  },
};
export const 失敗時は案内にフォーカスする: Story = {
  args: { error: "入力内容を確認してください。" },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole("alert")).toHaveFocus();
  },
};
