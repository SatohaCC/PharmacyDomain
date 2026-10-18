import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { UserRegistrationView } from "./user-registration-view";
const meta = {
  title: "画面/ユーザー登録",
  component: UserRegistrationView,
  args: {
    corporateId: "example",
    stores: [{ id: "example-store", name: "テスト薬局" }],
    staffs: [],
    personMode: "new",
    setPersonMode: fn(),
    role: "corporate_admin",
    setRole: fn(),
    staffMode: "existing",
    setStaffMode: fn(),
    snapshot: {},
    frozen: false,
    registrationSubmission: { submit: fn(), pending: false, blocked: false },
  },
} satisfies Meta<typeof UserRegistrationView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {};
export const 店舗ユーザー: Story = { args: { role: "store_viewer" } };
export const 部分成功: Story = {
  args: {
    snapshot: { personId: "example-person" },
    frozen: true,
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
    snapshot: { personId: "example-person", uncertain: true },
    frozen: true,
    registrationSubmission: {
      submit: fn(),
      pending: false,
      blocked: true,
      error: "前回の処理結果を確認してください。",
    },
  },
};
export const 登録完了: Story = {
  args: { issued: { id: "test-account", login_id: "test-admin" } },
};
