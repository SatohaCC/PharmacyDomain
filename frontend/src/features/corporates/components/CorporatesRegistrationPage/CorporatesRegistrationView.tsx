import { Panel } from "../../../../shared/ui/Panel";
import {
  Heading,
  Paragraph,
  Row,
  Subheading,
} from "../../../../shared/ui/Elements";
import type { Submission } from "../../../../shared/forms/submission";
import { Form } from "../../../../shared/component/Form";
import { TextField as Field } from "../../../../shared/ui/TextField";

export function CorporateRegistrationView({
  onSubmit,
}: {
  onSubmit: Submission;
}) {
  return (
    <>
      <Heading>新規契約登録</Heading>
      <Paragraph>法人と初期管理者の登録をまとめて完了します。</Paragraph>
      <Panel>
        <Form {...onSubmit} onSubmit={onSubmit.submit}>
          <Field name="name" label="法人名" required />
          <Row>
            <Field name="last" label="代表者の姓" required />
            <Field name="first" label="代表者の名" required />
          </Row>
          <Subheading>初期管理者</Subheading>
          <Row>
            <Field name="admin_last" label="管理者の姓" required />
            <Field name="admin_first" label="管理者の名" required />
          </Row>
          <Row>
            <Field name="admin_last_kana" label="管理者の姓（カナ）" required />
            <Field
              name="admin_first_kana"
              label="管理者の名（カナ）"
              required
            />
          </Row>
          <Field
            name="login_id"
            label="ログインID"
            required
            description="3～64文字の半角英数字・ピリオド・ハイフン・下線"
          />
          <Field
            name="email"
            label="連絡先メールアドレス（任意）"
            type="email"
          />
          <Field
            name="initial_password"
            label="初期パスワード"
            type="password"
            required
            description="15文字以上128文字以下。初回ログイン時に変更します。"
          />
        </Form>
      </Panel>
    </>
  );
}
