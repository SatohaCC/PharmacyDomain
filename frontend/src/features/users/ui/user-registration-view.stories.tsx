import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { UserRegistrationView } from "./user-registration-view";
const meta = {
  title: "画面/ユーザー登録と招待",
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
    status: "",
    copied: false,
    frozen: false,
    statusSubmission: { submit: fn(), pending: false, blocked: false },
    invitationSubmission: { submit: fn(), pending: false, blocked: false },
    copyInvitation: fn().mockResolvedValue(undefined),
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
    invitationSubmission: {
      submit: fn(),
      pending: false,
      blocked: false,
      error:
        "招待を発行できませんでした。入力内容を確認して再試行してください。",
    },
  },
};
export const 応答不明: Story = {
  args: {
    snapshot: { personId: "example-person", uncertain: true },
    frozen: true,
    invitationSubmission: {
      submit: fn(),
      pending: false,
      blocked: true,
      error: "前回の処理結果を確認してください。",
    },
  },
};
export const 発行済み: Story = {
  args: {
    invitationUrl:
      "https://example.invalid/invitations/accept#secret=invalid-story-sample",
    issued: { id: "example-invitation", secret: "invalid-story-sample" },
  },
};
