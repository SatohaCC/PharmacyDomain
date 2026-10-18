import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, userEvent, within } from "storybook/test";
import { CorporateRegistrationView } from "./corporates-registration-view";
const meta = {
  title: "画面/法人登録",
  component: CorporateRegistrationView,
  args: { onSubmit: { submit: fn(), pending: false, blocked: false } },
} satisfies Meta<typeof CorporateRegistrationView>;
export default meta;
type Story = StoryObj<typeof meta>;
export const 通常: Story = {
  play: async ({ canvasElement, args }) => {
    const c = within(canvasElement);
    await userEvent.type(c.getByLabelText(/法人名/), "テスト薬局");
    await userEvent.type(c.getByLabelText(/代表者の姓/), "テスト");
    await userEvent.type(c.getByLabelText(/代表者の名/), "太郎");
    await userEvent.type(c.getByLabelText(/^管理者の姓(?:必須| 必須)?$/), "テスト");
    await userEvent.type(c.getByLabelText(/^管理者の名(?:必須| 必須)?$/), "花子");
    await userEvent.type(c.getByLabelText(/管理者の姓（カナ）/), "テスト");
    await userEvent.type(c.getByLabelText(/管理者の名（カナ）/), "ハナコ");
    await userEvent.type(c.getByLabelText(/ログインID/), "test-admin");
    await userEvent.type(c.getByLabelText(/初期パスワード/), "test-initial-password-12345");
    await userEvent.click(c.getByRole("button", { name: "登録する" }));
    await expect(args.onSubmit.submit).toHaveBeenCalledTimes(1);
  },
};
export const 処理中: Story = {
  args: { onSubmit: { submit: fn(), pending: true, blocked: false } },
};
export const 登録失敗: Story = {
  args: {
    onSubmit: {
      submit: fn(),
      pending: false,
      blocked: false,
      error: "競合が発生しました。入力内容と登録状態を確認してください。",
    },
  },
};
export const 応答不明: Story = {
  args: {
    onSubmit: {
      submit: fn(),
      pending: false,
      blocked: true,
      error: "通信が途切れました。登録状態を管理者へ確認してください。",
    },
  },
};
