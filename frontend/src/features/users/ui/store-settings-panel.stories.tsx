import type { UserDetail } from "../model/user";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { StoreSettingsPanel } from "./store-settings-panel";
const meta = {
  title: "画面/店舗別の所属・権限・勤務時間",
  component: StoreSettingsPanel,
  args: {
    user: {
      id: "member-1",
      account_id: "account-1",
      person_id: "person-1",
      corporate_id: "corp-1",
      role: "member",
      status: "active",
      account_status: "active",
      staff_id: "staff-1",
      staff: null,
      store_ids: ["store-a", "store-b"],
      store_roles: [
        { store_id: "store-a", role: "store_operator" },
        { store_id: "store-b", role: "store_viewer" },
      ],
    } as UserDetail,
    stores: [
      { id: "store-a", name: "A薬局" },
      { id: "store-b", name: "B薬局" },
      { id: "store-c", name: "C薬局" },
    ],
    conditions: [],
    loading: false,
    appliedOn: "2026-11-03",
    onAppliedOnChange: fn(),
    onSave: fn(),
  },
} satisfies Meta<typeof StoreSettingsPanel>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 未登録: Story = {
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByText(/上限未確認/)).toBeVisible();
  },
};
export const 取得中: Story = { args: { loading: true } };
export const 取得失敗: Story = {
  args: { error: "勤務条件を取得できませんでした。" },
};
export const 店舗選択から時間設定: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を変更" }),
    );
    await expect(
      canvas.queryByLabelText("C薬局の週勤務時間（時間）"),
    ).not.toBeInTheDocument();
    await userEvent.click(canvas.getByRole("checkbox", { name: "C薬局" }));
    await expect(
      canvas.getByRole("button", { name: /C薬局の操作権限/ }),
    ).toBeVisible();
    await userEvent.type(
      canvas.getByLabelText("A薬局の週勤務時間（時間）"),
      "32",
    );
    await userEvent.type(
      canvas.getByLabelText("B薬局の週勤務時間（時間）"),
      "8",
    );
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を保存する" }),
    );
    await expect(args.onSave).toHaveBeenCalledWith(
      "member",
      [
        { store_id: "store-a", role: "store_operator" },
        { store_id: "store-b", role: "store_viewer" },
        { store_id: "store-c", role: "store_operator" },
      ],
      expect.arrayContaining([
        expect.objectContaining({ store_id: "store-a", weekly_hours: "32" }),
        expect.objectContaining({ store_id: "store-b", weekly_hours: "8" }),
      ]),
    );
  },
};
export const 保存失敗で入力保持: Story = {
  play: async ({ canvasElement, args }) => {
    args.onSave.mockRejectedValue(new Error("保存できませんでした。"));
    const canvas = within(canvasElement);
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を変更" }),
    );
    await userEvent.type(
      canvas.getByLabelText("A薬局の週勤務時間（時間）"),
      "32",
    );
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を保存する" }),
    );
    await expect(canvas.getByRole("alert")).toHaveTextContent(
      "保存できませんでした。",
    );
    await expect(
      canvas.getByLabelText("A薬局の週勤務時間（時間）"),
    ).toHaveValue("32");
  },
};

export const 応援スポット勤務表示: Story = {
  args: {
    conditions: [
      {
        store_id: "store-a",
        starts_on: "2026-11-01",
        ends_on: null,
        is_primary: true,
        is_managing_pharmacist: false,
        current: {
          effective_from: "2026-11-01",
          weekly_hours: "32",
          duty: "pharmacist",
          recorded_at: "2026-11-01T00:00:00Z",
          recorded_by: "admin",
        },
        history: [],
      },
      {
        store_id: "store-b",
        starts_on: "2026-11-05",
        ends_on: null,
        is_primary: false,
        is_managing_pharmacist: false,
        current: null, // 応援・スポットのため勤務時間未登録
        history: [],
      },
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText("未登録（応援・スポット等）")).toBeVisible();
    await expect(canvas.getByText("32時間")).toBeVisible();
  },
};

export const 合計超過では保存しない: Story = {
  args: {
    user: {
      ...meta.args.user,
      staff: {
        id: "staff-1",
        corporate_id: "corp-1",
        last_name: "薬局",
        first_name: "花子",
        last_name_kana: "ヤッキョク",
        first_name_kana: "ハナコ",
        job_title: null,
        code: null,
        phone_number: null,
        email: null,
        employment_type: "regular",
        weekly_contract_hours: 40,
        effective_weekly_hours: 40,
        effective_full_time_equivalent: 1,
        is_active: true,
        is_pharmacist: true,
      },
    },
  },
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement);
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を変更" }),
    );
    await userEvent.type(
      canvas.getByLabelText("A薬局の週勤務時間（時間）"),
      "32",
    );
    await userEvent.type(
      canvas.getByLabelText("B薬局の週勤務時間（時間）"),
      "8.01",
    );
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を保存する" }),
    );
    await expect(canvas.getByRole("alert")).toHaveTextContent("合計");
    await expect(args.onSave).not.toHaveBeenCalled();
    await userEvent.clear(canvas.getByLabelText("B薬局の週勤務時間（時間）"));
    await userEvent.type(
      canvas.getByLabelText("B薬局の週勤務時間（時間）"),
      "8",
    );
    await userEvent.click(
      canvas.getByRole("button", { name: "所属・権限・勤務時間を保存する" }),
    );
    await expect(args.onSave).toHaveBeenCalledTimes(1);
  },
};
