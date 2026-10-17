import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { Alert } from "../../../shared/ui/feedback/alert";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Button } from "../../../shared/ui/controls/button";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  FieldLabel,
  TextArea,
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
  copyError,
  invitationUrl,
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
  status,
  copied,
  frozen,
  statusSubmission,
  invitationSubmission,
  copyInvitation,
}: RegistrationViewProps) {
  if (issued)
    return (
      <Panel>
        <Subheading>招待を発行しました</Subheading>
        <Paragraph>
          本人の受諾後にユーザー登録が完了します。メールは自動送信されません。
        </Paragraph>
        <Paragraph>
          招待ID: <code>{issued.id}</code>
        </Paragraph>
        <FieldLabel>
          招待URL（この画面を離れると再表示できません）
          <TextArea readOnly value={invitationUrl || ""} />
        </FieldLabel>
        <Button onAction={() => void copyInvitation()}>招待URLをコピー</Button>
        {copied && <Paragraph role="status">コピーしました。</Paragraph>}
        {copyError && <Alert>{copyError}</Alert>}
        <Form
          label="受諾状態を確認"
          {...statusSubmission}
          onSubmit={statusSubmission.submit}
        />
        {status && (
          <Paragraph role="status">
            招待状態:{" "}
            {status === "accepted"
              ? "受諾済み"
              : status === "cancelled"
                ? "取消済み"
                : "未受諾"}
          </Paragraph>
        )}
        <Link
          href={`/admin/corporates/${encodeURIComponent(corporateId)}/users`}
        >
          ユーザー一覧へ
        </Link>
      </Panel>
    );
  return (
    <Panel>
      <Subheading>ユーザー登録・招待</Subheading>
      <Paragraph>
        本人を登録し、法人の利用権限を招待します。パスワードは設定しません。
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
          。この段階から招待を再試行します。
        </Notice>
      )}
      {snapshot.uncertain && (
        <Paragraph role="alert">
          前回の処理結果が不明です。重複登録を避けるため再送を止めています。管理者へ確認してください。
        </Paragraph>
      )}
      <Form
        label="招待を発行する"
        {...invitationSubmission}
        onSubmit={invitationSubmission.submit}
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
        {role !== "corporate_admin" && (
          <>
            <FieldGroup>
              許可する店舗
              {stores.map((s) => (
                <Checkbox
                  key={s.id}
                  name="store_ids"
                  value={s.id}
                  label={s.name}
                />
              ))}
              {!stores.length && (
                <Paragraph>先に店舗を登録してください。</Paragraph>
              )}
            </FieldGroup>
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
        <SectionHeading>3. 招待</SectionHeading>
        <Field
          name="addressee"
          label="宛先メールアドレス"
          type="email"
          required
        />
        <Field
          name="expires_at"
          label="招待期限（端末の現地時刻）"
          type="datetime-local"
          required
        />
        <Paragraph>
          登録は段階ごとに保存されます。途中で閉じた場合、作成済みの本人をこの画面から検索・復元することはできません。
        </Paragraph>
      </Form>
    </Panel>
  );
}
