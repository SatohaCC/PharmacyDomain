import { Panel } from "../../../shared/ui/layout/panel";
import {
  Entry,
  Eyebrow,
  Heading,
  Paragraph,
  Subheading,
} from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
export interface LoginViewProps {
  loginSubmission: Submission;
  tokenSubmission: Submission;
  passwordChangeRequired: boolean;
  authenticated: boolean;
}
export function LoginView({
  loginSubmission,
  tokenSubmission,
  passwordChangeRequired,
}: LoginViewProps) {
  return (
    <Entry>
      <Eyebrow>PHARMACY DOMAIN</Eyebrow>
      <Heading>
        {passwordChangeRequired ? "初回パスワード変更" : "管理画面にログイン"}
      </Heading>
      <Paragraph>
        {passwordChangeRequired
          ? "ご自身の新しいパスワードに変更すると利用を開始できます。"
          : "発行されたログインIDとパスワードを入力してください。"}
      </Paragraph>
      <Form
        key={passwordChangeRequired ? "change" : "login"}
        label={
          passwordChangeRequired ? "パスワードを変更して利用開始" : "ログイン"
        }
        {...loginSubmission}
        onSubmit={loginSubmission.submit}
      >
        {!passwordChangeRequired && (
          <>
            <Field name="corporate_id" label="法人ID" required />
            <Field name="email" label="メールアドレス" type="email" required />
          </>
        )}
        <Field
          name="password"
          label={passwordChangeRequired ? "新しいパスワード" : "パスワード"}
          type="password"
          required
          description={
            passwordChangeRequired ? "15文字以上128文字以下" : undefined
          }
        />
        {passwordChangeRequired && (
          <Field
            name="confirmation"
            label="新しいパスワード（確認）"
            type="password"
            required
          />
        )}
      </Form>
      {import.meta.env.DEV && (
        <Panel>
          <Subheading>開発用の接続</Subheading>
          <Paragraph>
            取得済みBearerトークンをこの画面内だけで利用します。再読込すると消去されます。
          </Paragraph>
          <Form
            label="接続する"
            {...tokenSubmission}
            onSubmit={tokenSubmission.submit}
          >
            <Field
              name="token"
              label="Bearerトークン"
              type="password"
              required
            />
          </Form>
        </Panel>
      )}
    </Entry>
  );
}
