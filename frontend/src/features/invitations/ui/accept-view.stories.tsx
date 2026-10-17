import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { AcceptView } from "./accept-view";
const meta = {
  title: "画面/招待受諾",
  component: AcceptView,
  parameters: { standalone: true },
  args: {
    secret: "invalid-story-sample",
    done: false,
    corporate: null,
    accepted: false,
    uncertain: false,
    loginSubmission: { submit: fn(), pending: false, blocked: false },
    acceptanceSubmission: { submit: fn(), pending: false, blocked: false },
    oidcAvailable: true,
    authenticated: true,
  },
} satisfies Meta<typeof AcceptView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {};
export const 未ログイン: Story = { args: { authenticated: false } };
export const 受諾失敗: Story = {
  args: {
    acceptanceSubmission: {
      submit: fn(),
      pending: false,
      blocked: false,
      error: "この招待は利用できません。発行した管理者へ確認してください。",
    },
  },
};
export const 応答不明: Story = {
  args: {
    uncertain: true,
    acceptanceSubmission: {
      submit: fn(),
      pending: false,
      blocked: true,
      error: "前回の結果が不明です。管理者へ確認してください。",
    },
  },
};
export const 完了: Story = { args: { done: true } };
