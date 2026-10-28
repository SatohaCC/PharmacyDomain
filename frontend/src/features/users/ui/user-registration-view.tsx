import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  Notice,
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
  staffs,
  personMode,
  setPersonMode,
  role,
  setRole,
  staffMode,
  setStaffMode,
  snapshot,
  issued,
  frozen,
  registrationSubmission,
}: RegistrationViewProps) {
  if (issued)
    return (
      <Panel>
        <Subheading>ユーザー登録が完了しました</Subheading>
        <Paragraph>
          ログインID: <code>{issued.login_id}</code>
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
  return (
    <Panel>
      <Subheading>ユーザー登録</Subheading>
      <Paragraph>
        本人・ログインID・初期パスワードを登録し、法人の利用権限を確定します。
      </Paragraph>
      {snapshot.personId && (
        <Notice>
          本人登録済み: <code>{snapshot.personId}</code>
          {snapshot.staffId && (
            <>
              {" "}
              ／スタッフ: <code>{snapshot.staffId}</code>
            </>
          )}
          {snapshot.linked && " ／本人紐付け済み"}
          。この段階からアカウント登録を再試行します。
        </Notice>
      )}
      {snapshot.uncertain && (
        <Paragraph role="alert">
          前回の処理結果が不明です。重複登録を避けるため再送を止めています。管理者へ確認してください。
        </Paragraph>
      )}
      <Form
        label="ユーザーを登録する"
        {...registrationSubmission}
        onSubmit={registrationSubmission.submit}
      >
        <SectionHeading>1. 本人情報</SectionHeading>
        <SelectField
          label="本人の指定"
          value={personMode}
          disabled={frozen}
          onValueChange={setPersonMode}
          options={[
            { value: "new", label: "新しく本人を登録" },
            { value: "existing", label: "登録済みの本人IDを指定" },
          ]}
        />
        {personMode === "existing" ? (
          <Field
            name="person_id"
            label="本人ID"
            required
            readOnly={!!snapshot.personId}
          />
        ) : null}
        {(personMode === "new" ||
          (role !== "corporate_admin" && staffMode === "new")) && (
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
                readOnly={!!snapshot.personId}
              />
            ))}
          </Row>
        )}
        <SectionHeading>2. 法人での権限</SectionHeading>
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
          法人管理者にも店舗の利用権限を追加できます。管理薬剤師の管理権限は有効な任命から付与され、在任中は一店舗だけに勤務・所属できます。
        </Paragraph>
        {role === "corporate_admin" && (
          <SelectField
            label="対応するスタッフ（任意）"
            name="staff_id"
            disabled={!!snapshot.linked}
            options={[
              { value: "", label: "指定しない" },
              ...staffs
                .filter((s) => s.is_active)
                .map((s) => ({
                  value: s.id,
                  label: s.last_name + " " + s.first_name,
                })),
            ]}
          />
        )}
        {role !== "corporate_admin" && (
          <>
            <SelectField
              label="スタッフの指定"
              disabled={frozen}
              value={staffMode}
              onValueChange={setStaffMode}
              options={[
                { value: "existing", label: "既存スタッフを選択" },
                { value: "new", label: "スタッフを新規登録" },
              ]}
            />
            {staffMode === "existing" ? (
              <SelectField
                label="スタッフ"
                name="staff_id"
                required
                disabled={!!snapshot.linked}
                options={staffs
                  .filter((s) => s.is_active)
                  .map((s) => ({
                    value: s.id,
                    label: s.last_name + " " + s.first_name,
                  }))}
              />
            ) : (
              <>
                <SelectField
                  label="主所属店舗"
                  name="home_store"
                  required
                  options={stores.map((s) => ({ value: s.id, label: s.name }))}
                />
                <Field
                  name="start_date"
                  label="所属開始日"
                  type="date"
                  required
                />
              </>
            )}
          </>
        )}
        <SectionHeading>3. ログイン情報</SectionHeading>
        <Field
          name="login_id"
          label="ログインID"
          required
          description="3～64文字の半角英数字・ピリオド・ハイフン・下線"
        />
        <Field
          name="initial_password"
          label="初期パスワード"
          type="password"
          required
          description="15文字以上128文字以下。本人に安全な方法でお渡しください。"
        />
        <Paragraph>
          登録は段階ごとに保存されます。途中で閉じた場合、作成済みの本人をこの画面から検索・復元することはできません。
        </Paragraph>
      </Form>
    </Panel>
  );
}
