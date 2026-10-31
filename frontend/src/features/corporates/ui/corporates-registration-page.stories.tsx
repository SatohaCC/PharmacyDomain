import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, userEvent, within } from "storybook/test";
import { useSubmission } from "../../../shared/forms/use-submission";
import { CorporateRegistrationView } from "./corporates-registration-view";
function FailedRegistration() {
  const state = useSubmission(async () => {
    throw new Error("登録できませんでした。");
  });
  return <CorporateRegistrationView onSubmit={state} />;
}
const meta = {
  title: "画面/法人登録の接続",
  component: FailedRegistration,
} satisfies Meta<typeof FailedRegistration>;
export default meta;
export const 失敗しても入力を保持する: StoryObj<typeof meta> = {
  play: async ({ canvasElement }) => {
    const c = within(canvasElement);
    await userEvent.type(c.getByLabelText(/法人名/), "テスト薬局");
    await userEvent.type(c.getByLabelText(/代表者の姓/), "テスト");
    await userEvent.type(c.getByLabelText(/代表者の名/), "太郎");
    await userEvent.type(
      c.getByLabelText(/^管理者の姓(?:必須| 必須)?$/),
      "テスト",
    );
    await userEvent.type(
      c.getByLabelText(/^管理者の名(?:必須| 必須)?$/),
      "花子",
    );
    await userEvent.type(c.getByLabelText(/管理者の姓（カナ）/), "テスト");
    await userEvent.type(c.getByLabelText(/管理者の名（カナ）/), "ハナコ");
    await userEvent.type(c.getByLabelText(/メールアドレス/), "test-admin@example.com");
    await userEvent.type(
      c.getByLabelText(/初期パスワード/),
      "test-initial-password-12345",
    );
    await userEvent.click(c.getByRole("button", { name: "登録する" }));
    await expect(c.getByRole("alert")).toHaveTextContent(
      "登録できませんでした。",
    );
    await expect(c.getByLabelText(/法人名/)).toHaveValue("テスト薬局");
  },
};
