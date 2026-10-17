import { Panel } from "../../../shared/ui/layout/panel";
import {
  Entry,
  Eyebrow,
  Heading,
  Paragraph,
  Notice,
  Subheading,
} from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
export interface LoginViewProps {
  loginSubmission: Submission;
  tokenSubmission: Submission;
  oidcAvailable: boolean;
  authenticated: boolean;
}
export function LoginView({
  loginSubmission,
  tokenSubmission,
  oidcAvailable,
}: LoginViewProps) {
  return (
    <Entry>
      <Eyebrow>PHARMACY DOMAIN</Eyebrow>
      <Heading>管理画面にログイン</Heading>
      <Paragraph>法人・店舗・ユーザーを管理します。</Paragraph>
      {oidcAvailable ? (
        <Form
          label="ログイン"
          {...loginSubmission}
          onSubmit={loginSubmission.submit}
        />
      ) : (
        <Notice>
          認証接続先が未設定です。OIDCの環境変数を設定してください。
        </Notice>
      )}
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
