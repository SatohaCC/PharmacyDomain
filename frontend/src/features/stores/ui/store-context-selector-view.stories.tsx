import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { StoreContextSelectorView } from "./store-context-selector-view";

const meta = {
  title: "店舗/操作/店舗切替セレクタ",
  component: StoreContextSelectorView,
  args: {
    stores: [
      { id: "store-a1", name: "テスト薬局 本店", code: "A01" },
      { id: "store-a2", name: "テスト薬局 駅前店", code: "A02" },
    ],
    selectedStoreId: "store-a1",
    onSelectStore: fn(),
    disabled: false,
  },
} satisfies Meta<typeof StoreContextSelectorView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const 正常表示: Story = {};

export const 店舗切替操作: Story = {
  play: async ({ canvasElement, args }) => {
    const trigger = within(canvasElement).getByRole("button", {
      name: "勤務店舗",
    });
    await userEvent.click(trigger);
    const option = within(document.body).getByRole("option", {
      name: /テスト薬局 駅前店/,
    });
    await userEvent.click(option);
    await expect(args.onSelectStore).toHaveBeenCalledWith("store-a2");
  },
};

export const 未選択状態: Story = {
  args: {
    selectedStoreId: null,
  },
};

export const 候補なし: Story = {
  args: {
    stores: [],
    selectedStoreId: null,
  },
};
