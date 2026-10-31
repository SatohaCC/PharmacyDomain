import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  SectionHeading,
  Row,
  FieldGroup,
} from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
import type { RegistrationViewProps } from "../model/registration";
export function UserRegistrationView({
  corporateId,
  stores,
  role,
  setRole,
  issued,
  registrationSubmission,
}: RegistrationViewProps) {
  if (issued)
    return (
      <Panel>
        <Subheading>ユーザー登録が完了しました</Subheading>
        <Paragraph>
          メールアドレス: <code>{issued.email}</code>
        </Paragraph>
        <Paragraph>
          初期パスワードを本人へお渡しください。初回ログイン時にパスワードの変更が必要です。
        </Paragraph>
        <Link
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/users`}
        >
          ユーザー一覧へ
        </Link>
      </Panel>
    );
  const frozen =
    registrationSubmission.pending || registrationSubmission.blocked;
  return (
    <Panel>
      <Subheading>ユーザー登録</Subheading>
      <Paragraph>
        本人・スタッフ・アカウント・法人の利用権限をまとめて新規登録します。
      </Paragraph>
      <Form
        label="ユーザーを登録する"
        {...registrationSubmission}
        onSubmit={registrationSubmission.submit}
      >
        <SectionHeading>1. 本人・スタッフ情報</SectionHeading>
        <Row>
          {[
            ["last_name", "姓"],
            ["first_name", "名"],
            ["last_name_kana", "姓カナ"],
            ["first_name_kana", "名カナ"],
          ].map(([name, label]) => (
            <Field
              key={name}
              name={name}
              label={label}
              required
              readOnly={frozen}
            />
          ))}
        </Row>
        <SectionHeading>2. 法人での権限と所属</SectionHeading>
        <SelectField
          label="ロール"
          value={role}
          disabled={frozen}
          onValueChange={(value) => setRole(value as typeof role)}
          options={[
            { value: "corporate_admin", label: "法人管理者" },
            { value: "store_operator", label: "店舗操作者" },
            { value: "store_viewer", label: "店舗閲覧者" },
          ]}
        />
        <FieldGroup>
          店舗の利用権限
          {stores.map((s) => (
            <Checkbox
              key={s.id}
              name="store_ids"
              value={s.id}
              label={s.name}
              readOnly={frozen}
            />
          ))}
          {!stores.length && (
            <Paragraph>先に店舗を登録してください。</Paragraph>
          )}
        </FieldGroup>
        <Paragraph>
          法人管理者にも店舗の利用権限を追加できます。店舗で勤務する場合は主所属店舗と所属開始日も指定してください。
        </Paragraph>
        <SelectField
          label="主所属店舗"
          name="home_store"
          required={role !== "corporate_admin"}
          disabled={frozen}
          options={[
            ...(role === "corporate_admin"
              ? [{ value: "", label: "指定しない" }]
              : []),
            ...stores.map((s) => ({ value: s.id, label: s.name })),
          ]}
        />
        <Field
          name="start_date"
          label="所属開始日"
          type="date"
          required={role !== "corporate_admin"}
          readOnly={frozen}
        />
        <SectionHeading>3. ログイン情報</SectionHeading>
        <Field
          name="email"
          label="メールアドレス"
          type="email"
          required
          readOnly={frozen}
        />
        <Field
          name="initial_password"
          label="初期パスワード"
          type="password"
          required
          readOnly={frozen}
          description="15文字以上128文字以下。本人に安全な方法でお渡しください。"
        />
      </Form>
    </Panel>
  );
}
