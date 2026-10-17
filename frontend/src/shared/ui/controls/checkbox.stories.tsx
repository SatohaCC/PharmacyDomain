import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";
import { Checkbox } from "./checkbox";
const meta = {
  title: "共通UI/操作/チェック",
  component: Checkbox,
  args: { name: "stores", value: "example-store", label: "テスト薬局" },
} satisfies Meta<typeof Checkbox>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 操作: Story = {
  play: async ({ canvasElement }) => {
    const field = within(canvasElement).getByRole("checkbox", {
      name: "テスト薬局",
    });
    await userEvent.click(field);
    await expect(field).toBeChecked();
  },
};
export const 無効: Story = { args: { disabled: true } };
