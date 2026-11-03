import { useState } from "react";
import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  Paragraph,
  SectionHeading,
  Row,
  FieldGroup,
  Details,
  Summary,
} from "../../../shared/ui/layout/elements";
import { Link } from "../../../shared/ui/navigation/link";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
import {
  EMPLOYMENT_TYPE_OPTIONS,
  type RegistrationViewProps,
} from "../model/registration";
export function UserRegistrationView({
  corporateId,
  stores,
  role,
  setRole,
  issued,
  registrationSubmission,
}: RegistrationViewProps) {
  const [selectedStoreIds, setSelectedStoreIds] = useState<string[]>([]);
  const [homeStore, setHomeStore] = useState("");
  const [contractHours, setContractHours] = useState("");
  const [storeHours, setStoreHours] = useState<Record<string, string>>({});
  const selectedStores = stores.filter((store) =>
    selectedStoreIds.includes(store.id),
  );
  if (issued)
    return (
      <Panel>
        <Subheading>ユーザー登録が完了しました</Subheading>
        <Paragraph>
          ログインID: <code>{issued.loginId}</code>
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
        <Row>
          <Field
            name="code"
            label="社員・スタッフ番号"
            readOnly={frozen}
            description="例: STF-001"
          />
          <Field
            name="job_title"
            label="役職・肩書"
            readOnly={frozen}
            description="例: 薬局長、チーフクラーク"
          />
        </Row>
        <SectionHeading>2. 労働契約・雇用区分</SectionHeading>
        <SelectField
          label="雇用形態"
          name="employment_type"
          defaultValue="regular"
          disabled={frozen}
          options={EMPLOYMENT_TYPE_OPTIONS}
        />
        <Field
          name="weekly_contract_hours"
          label="週所定労働時間（時間）"
          value={contractHours}
          onValueChange={setContractHours}
          readOnly={frozen}
          description="例: 40.0。スポット応援（ヘルプ）要員として事前届出・登録を行う場合は 0.0 を入力してください。"
        />
        <Details>
          <Summary>保有資格（任意）</Summary>
          <Row>
            <Field
              name="pharmacist_license_number"
              label="薬剤師免許番号"
              readOnly={frozen}
              description="調剤・鑑査業務や管理薬剤師要件に必要です。"
            />
            <Field
              name="registered_seller_number"
              label="登録販売者登録番号"
              readOnly={frozen}
            />
          </Row>
        </Details>
        <SectionHeading>3. 法人での権限と所属</SectionHeading>
        <SelectField
          label="ロール"
          value={role}
          disabled={frozen}
          onValueChange={(value) => setRole(value as typeof role)}
          options={[
            { value: "corporate_admin", label: "法人管理者" },
            { value: "member", label: "一般ユーザー" },
          ]}
        />
        <FieldGroup>
          <Subheading>① 所属店舗を選ぶ</Subheading>
          {stores.map((store) => (
            <Checkbox
              key={store.id}
              name="store_ids"
              value={store.id}
              label={store.name}
              isSelected={selectedStoreIds.includes(store.id)}
              onChange={(selected) =>
                setSelectedStoreIds((ids) =>
                  selected
                    ? [...ids, store.id]
                    : ids.filter((id) => id !== store.id),
                )
              }
              readOnly={frozen}
            />
          ))}
          {!stores.length && (
            <Paragraph>先に店舗を登録してください。</Paragraph>
          )}
        </FieldGroup>
        {!!selectedStores.length && (
          <>
            <SelectField
              label="主所属店舗"
              name="home_store"
              value={
                selectedStoreIds.includes(homeStore)
                  ? homeStore
                  : selectedStores[0]?.id || ""
              }
              onValueChange={setHomeStore}
              required
              disabled={frozen}
              options={selectedStores.map((store) => ({
                value: store.id,
                label: store.name,
              }))}
            />
            <Paragraph>
              店舗ごとに所属開始日・操作権限・週勤務時間・従事区分を設定してください。
            </Paragraph>
            {selectedStores.map((store) => (
              <FieldGroup key={store.id}>
                <Subheading>{store.name}</Subheading>
                <Field
                  name={`store_start_${store.id}`}
                  label={`${store.name}の所属開始日`}
                  type="date"
                  required
                  readOnly={frozen}
                />
                <SelectField
                  name={`store_role_${store.id}`}
                  label={`${store.name}の操作権限`}
                  defaultValue="store_operator"
                  disabled={frozen}
                  options={[
                    { value: "store_operator", label: "編集可能" },
                    { value: "store_viewer", label: "閲覧のみ" },
                  ]}
                />
                <Field
                  name={`store_hours_${store.id}`}
                  value={storeHours[store.id] || ""}
                  onValueChange={(value) =>
                    setStoreHours((hours) => ({ ...hours, [store.id]: value }))
                  }
                  label={`${store.name}の週勤務時間（時間）`}
                  readOnly={frozen}
                  description="0～168、小数第2位まで。空欄は未登録。"
                />
                <SelectField
                  name={`store_duty_${store.id}`}
                  label={`${store.name}の従事区分`}
                  defaultValue="other"
                  disabled={frozen}
                  options={[
                    { value: "pharmacist", label: "薬剤師" },
                    { value: "registered_seller", label: "登録販売者" },
                    { value: "other", label: "その他" },
                  ]}
                />
              </FieldGroup>
            ))}
          </>
        )}
        <Paragraph>
          法人管理者にも店舗の利用権限を追加できます。選択した店舗に主所属・兼務所属と勤務条件をまとめて登録します。
        </Paragraph>
        {!!selectedStores.length && (
          <Paragraph>
            登録済みの週勤務時間の合計：
            {selectedStores.reduce(
              (sum, store) =>
                sum + Math.round((Number(storeHours[store.id]) || 0) * 100),
              0,
            ) / 100}
            時間 ／ 週所定労働時間：{contractHours || "未登録（上限未確認）"}
            {contractHours ? "時間" : ""}
            {selectedStores.some((store) => !storeHours[store.id]?.trim()) &&
              "（勤務時間が未登録の店舗があります）"}
          </Paragraph>
        )}
        <SectionHeading>4. ログイン情報</SectionHeading>
        <Field name="login_id" label="ログインID" required readOnly={frozen} />
        <Field
          name="email"
          label="連絡先メールアドレス（任意）"
          type="email"
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
