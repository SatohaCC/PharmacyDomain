import type { Meta, StoryObj } from "@storybook/react-vite";
import type { MedicationHistoryBlockInput } from "../model/block";
import { BlocksEditorView } from "./blocks-editor-view";

const meta: Meta<typeof BlocksEditorView> = {
  title: "Features/MedicationHistory/BlocksEditorView",
  component: BlocksEditorView,
};

export default meta;
type Story = StoryObj<typeof BlocksEditorView>;

export const Default: Story = {
  args: {
    isDraft: true,
    initialBlocks: [
      {
        clientKey: "block-1",
        id: "b1",
        category_code: "s",
        category_name: "S（主観的情報）",
        category_badge_label: "S",
        content: "先週から花粉症の症状が出始め、鼻水と目のかゆみが強い。",
        display_order: 10,
        source_module: "soap",
      },
      {
        clientKey: "block-2",
        id: "b2",
        category_code: "o",
        category_name: "O（客観的情報）",
        category_badge_label: "O",
        content: "前回処方: アレグラ錠60mg 1回1錠 1日2回 朝夕食後 14日分。残薬なし。",
        display_order: 20,
        source_module: "soap",
      },
      {
        clientKey: "block-3",
        id: "b3",
        category_code: "a",
        category_name: "A（評価・判断）",
        category_badge_label: "A",
        content: "症状悪化に伴い点鼻薬併用が望ましいと判断。",
        display_order: 30,
        source_module: "soap",
      },
      {
        clientKey: "block-4",
        id: "b4",
        category_code: "p",
        category_name: "P（計画）",
        category_badge_label: "P",
        content: "用法用量の遵守および点鼻薬の噴霧手技を指導。次回効果確認予定。",
        display_order: 40,
        source_module: "soap",
      },
    ],
    hearingItems: [
      {
        field_id: "h1",
        label: "症状・体調変化",
        value: "花粉症悪化、鼻づまりあり",
      },
      {
        field_id: "h2",
        label: "残薬の有無",
        value: "残薬なし",
      },
    ],
    onSave: async (blocks: MedicationHistoryBlockInput[]) => {
      console.log("Saved blocks:", blocks);
    },
  },
};

export const EmptyBlocks: Story = {
  args: {
    isDraft: true,
    initialBlocks: [],
    hearingItems: [
      {
        field_id: "h1",
        label: "体調確認",
        value: "",
      },
    ],
  },
};

export const ReadOnly: Story = {
  args: {
    isDraft: false,
    readOnly: true,
    initialBlocks: [
      {
        clientKey: "b1",
        category_code: "s",
        category_name: "S（主観的情報）",
        category_badge_label: "S",
        content: "熱や咳などの症状は治まったとのこと。",
        display_order: 10,
        source_module: "soap",
      },
    ],
  },
};
