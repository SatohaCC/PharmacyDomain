import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import type { MedicationHistoryBlockInput } from "../model/block";
import type { FinalizeMedicationHistoryInput } from "../model/finalization";
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


export const FinalizationReview: Story = {
  args: {
    isDraft: true,
    initialBlocks: [],
    finalizationReview: {
      delayReasonRequired: true,
      advisoryWarnings: ["法定記載事項の確認結果に未確認項目があります。"],
      pendingExternalCorrections: [],
      onFinalize: fn(
        async (input: FinalizeMedicationHistoryInput) => input,
      ),
      onResidualGuidanceChange: fn(),
    },
  },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      canvas.getByRole("radio", { name: /残薬の発生要因を確認する/ }),
    );
    await userEvent.click(
      canvas.getByRole("radio", {
        name: /薬学的評価と指導内容を記録した/,
      }),
    );
    await userEvent.type(
      canvas.getByLabelText("記載遅延理由（必須）"),
      "翌営業日に内容を再確認して確定した。",
    );
    canvas.getByRole("button", { name: "薬歴を確定" }).click();
    await expect(args.finalizationReview?.onFinalize).toHaveBeenCalledWith({
      review_result: "assessment_and_instruction_recorded",
      delay_reason: "翌営業日に内容を再確認して確定した。",
    });
    await canvas.findByText("薬歴を確定しました。");
    await expect(
      canvas.getByRole("button", { name: "薬歴を確定" }),
    ).toBeEnabled();
    await expect(
      args.finalizationReview?.onResidualGuidanceChange,
    ).toHaveBeenCalledWith("review_cause");
  },
};

export const PendingCorrectionBlocksFinalization: Story = {
  args: {
    isDraft: true,
    initialBlocks: [],
    finalizationReview: {
      pendingExternalCorrections: [
        {
          correction_id: "correction-1",
          reason: "処方内容の更新を確認してください。",
          status: "investigating",
        },
      ],
      onFinalize: fn(
        async (input: FinalizeMedicationHistoryInput) => input,
      ),
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      canvas.getByRole("radio", {
        name: /薬学的評価と指導内容を記録した/,
      }),
    );
    await expect(
      canvas.getByRole("button", { name: "薬歴を確定" }),
    ).toBeDisabled();
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
