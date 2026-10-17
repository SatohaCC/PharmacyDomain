import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within, waitFor } from "storybook/test";
import { SelectField } from "./select-field";
const meta = {
  title: "共通UI/操作/選択",
  component: SelectField,
  args: {
    label: "権限",
    options: [
      { value: "admin", label: "法人管理者" },
      { value: "viewer", label: "店舗閲覧者" },
    ],
    onValueChange: fn(),
  },
} satisfies Meta<typeof SelectField>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 選択操作: Story = {
  play: async ({ canvasElement, args }) => {
    const trigger = within(canvasElement).getByRole("button");
    await userEvent.click(trigger);
    await userEvent.click(
      within(document.body).getByRole("option", { name: "店舗閲覧者" }),
    );
    await expect(args.onValueChange).toHaveBeenCalledWith("viewer");
    await expect(trigger).toHaveFocus();
  },
};
export const キーボードと閉じる操作: Story = {
  play: async ({ canvasElement }) => {
    const trigger = within(canvasElement).getByRole("button");
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    await expect(within(document.body).getByRole("listbox")).toBeVisible();
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(trigger).toHaveFocus());
  },
};
export const 無効: Story = { args: { disabled: true } };
