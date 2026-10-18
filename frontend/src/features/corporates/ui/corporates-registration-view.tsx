import { Panel } from "../../../shared/ui/layout/panel";
import {
  Heading,
  Paragraph,
  Row,
  Subheading,
} from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
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
          <Field name="login_id" label="ログインID" required />
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
