import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { Button } from "./button";
const meta = {
  title: "共通UI/操作/ボタン",
  component: Button,
  args: { children: "登録する", onAction: fn() },
} satisfies Meta<typeof Button>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    await userEvent.click(c.getByRole("button", { name: "登録する" }));
    await expect(args.onAction).toHaveBeenCalledTimes(1);
  },
};
export const 無効: Story = {
  args: { disabled: true },
  play: async ({ canvasElement, args }) => {
    const b = within(canvasElement).getByRole("button");
    await expect(b).toBeDisabled();
    await userEvent.click(b);
    await expect(args.onAction).not.toHaveBeenCalled();
  },
};
export const 処理中: Story = {
  args: { pending: true, children: "処理中…" },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole("button")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  },
};
export const 補助操作: Story = {
  args: { variant: "secondary", children: "キャンセル" },
};
export const キーボード操作: Story = {
  play: async ({ canvasElement, args }) => {
    const b = within(canvasElement).getByRole("button");
    b.focus();
    await userEvent.keyboard("{Enter}");
    await expect(args.onAction).toHaveBeenCalledTimes(1);
  },
};
