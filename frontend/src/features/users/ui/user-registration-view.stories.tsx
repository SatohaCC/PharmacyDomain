import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { UserRegistrationView } from "./user-registration-view";
const meta = {
  title: "画面/ユーザー登録",
  component: UserRegistrationView,
  args: {
    corporateId: "example",
    stores: [{ id: "example-store", name: "テスト薬局" }],
    role: "corporate_admin",
    setRole: fn(),
    registrationSubmission: { submit: fn(), pending: false, blocked: false },
  },
} satisfies Meta<typeof UserRegistrationView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {};
export const 法人管理者と店舗利用権限: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const store = canvas.getByRole("checkbox", { name: "テスト薬局" });
    await userEvent.click(store);
    await expect(store).toBeChecked();
    await expect(
      canvas.getByText("法人管理者にも店舗の利用権限を追加できます。", {
        exact: false,
      }),
    ).toBeVisible();
  },
};
export const 店舗ユーザー: Story = { args: { role: "member" } };
export const 登録失敗: Story = {
  args: {
    registrationSubmission: {
      submit: fn(),
      pending: false,
      blocked: false,
      error: "登録できませんでした。入力内容を確認して再試行してください。",
    },
  },
};
export const 応答不明: Story = {
  args: {
    registrationSubmission: {
      submit: fn(),
      pending: false,
      blocked: true,
      error: "前回の処理結果を確認してください。",
    },
  },
};
export const 登録完了: Story = {
  args: { issued: { id: "test-account", loginId: "test-admin" } },
};

export const 所属店舗から権限と勤務時間を設定する: Story = {
  args: {
    stores: [
      { id: "store-a", name: "A薬局" },
      { id: "store-b", name: "B薬局" },
    ],
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      canvas.queryByLabelText("A薬局の週勤務時間（時間）"),
    ).not.toBeInTheDocument();
    await userEvent.click(canvas.getByRole("checkbox", { name: "A薬局" }));
    await userEvent.click(canvas.getByRole("checkbox", { name: "B薬局" }));
    await expect(
      canvas.getByRole("button", { name: /A薬局の操作権限/ }),
    ).toBeVisible();
    await expect(
      canvas.getByRole("button", { name: /B薬局の操作権限/ }),
    ).toBeVisible();
    await userEvent.type(
      canvas.getByLabelText("A薬局の週勤務時間（時間）"),
      "32",
    );
    await userEvent.type(
      canvas.getByLabelText("B薬局の週勤務時間（時間）"),
      "8",
    );
    await userEvent.click(canvas.getByRole("checkbox", { name: "B薬局" }));
    await expect(
      canvas.queryByLabelText("B薬局の週勤務時間（時間）"),
    ).not.toBeInTheDocument();
  },
};
