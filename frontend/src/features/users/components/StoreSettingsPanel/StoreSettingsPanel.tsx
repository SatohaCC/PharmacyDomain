import { assessStoreHoursBudget } from "../../model/store-hours-budget";
import { useRef, useState } from "react";
import { Panel } from "../../../../shared/ui/Panel";
import {
  Paragraph,
  SectionHeading,
  Subheading,
  Row,
  FieldGroup,
  Details,
  Summary,
} from "../../../../shared/ui/Elements";
import { Checkbox } from "../../../../shared/ui/Checkbox";
import { SelectField } from "../../../../shared/ui/SelectField";
import { TextField } from "../../../../shared/ui/TextField";
import { Button } from "../../../../shared/ui/Button";
import { Alert } from "../../../../shared/ui/Alert";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../../shared/ui/Table";
import type { StoreAffiliation } from "../../model/store-work-conditions";
import type { UserDetail } from "../../model/user";

export type StoreConditionChange = {
  store_id: string;
  effective_from: string;
  starts_on: string;
  weekly_hours: string | null;
  duty: string;
};
export type SaveStoreSettings = (
  role: string,
  stores: { store_id: string; role: string }[],
  conditions: StoreConditionChange[],
) => Promise<void>;
const dutyOptions = [
  { value: "pharmacist", label: "薬剤師" },
  { value: "registered_seller", label: "登録販売者" },
  { value: "other", label: "その他" },
];
const dutyLabel = (value: string) =>
  dutyOptions.find((item) => item.value === value)?.label || value;
const roleLabel = (value: string) =>
  value === "store_viewer" ? "閲覧のみ" : "編集可能";
export const todayInJapan = () =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(
    new Date(),
  );

type Props = {
  user: UserDetail;
  stores: { id: string; name: string }[];
  conditions: StoreAffiliation[];
  loading: boolean;
  error?: string | null;
  appliedOn: string;
  onAppliedOnChange: (date: string) => void;
  onSave: SaveStoreSettings;
};

export function StoreSettingsPanel(props: Props) {
  const [editing, setEditing] = useState(false);
  const summaryBudget = assessStoreHoursBudget(
    props.user.staff?.weekly_contract_hours,
    [],
    props.conditions,
    props.appliedOn,
  );
  return (
    <Panel>
      <Row>
        <SectionHeading>所属店舗・権限・週勤務時間</SectionHeading>
        {!editing && (
          <Button
            variant="secondary"
            onAction={() => setEditing(true)}
            disabled={props.loading || !!props.error}
          >
            所属・権限・勤務時間を変更
          </Button>
        )}
      </Row>
      {props.error && <Alert tone="error">{props.error}</Alert>}
      {props.loading && <Paragraph>店舗の勤務条件を取得しています。</Paragraph>}
      {editing ? (
        <StoreSettingsForm
          {...props}
          onCancel={() => setEditing(false)}
          onSaved={() => setEditing(false)}
        />
      ) : (
        <>
          <Paragraph>
            法人権限：
            {props.user.role === "corporate_admin"
              ? "法人管理者"
              : "一般ユーザー"}
          </Paragraph>
          <TextField
            name="conditions_on"
            label="照会日"
            type="date"
            value={props.appliedOn}
            onValueChange={props.onAppliedOnChange}
            required
          />
          {!props.loading && !props.error && (
            <>
              {!props.user.store_roles.length && (
                <Paragraph>所属店舗は未設定です。</Paragraph>
              )}
              {props.user.staff_id && (
                <Paragraph>
                  登録済み週勤務時間の最大合計：{summaryBudget.maximumHours}時間
                  ／ 週所定労働時間：
                  {props.user.staff?.weekly_contract_hours == null
                    ? "未登録（上限未確認）"
                    : `${props.user.staff.weekly_contract_hours}時間`}
                  {summaryBudget.incomplete
                    ? "（応援・スポット勤務等で勤務時間が未登録の店舗があります）"
                    : ""}
                </Paragraph>
              )}
              <Table>
                <thead>
                  <tr>
                    <TableHeader>店舗</TableHeader>
                    <TableHeader>操作権限</TableHeader>
                    <TableHeader>週勤務時間</TableHeader>
                    <TableHeader>従事区分</TableHeader>
                  </tr>
                </thead>
                <tbody>
                  {props.user.store_roles.map((assignment) => {
                    const affiliation = props.conditions.find(
                      (item) =>
                        item.store_id === assignment.store_id &&
                        item.starts_on <= props.appliedOn &&
                        (!item.ends_on || props.appliedOn <= item.ends_on),
                    );
                    const current = affiliation?.current;
                    return (
                      <tr key={assignment.store_id}>
                        <TableCell>
                          {props.stores.find(
                            (store) => store.id === assignment.store_id,
                          )?.name || assignment.store_id}
                        </TableCell>
                        <TableCell>{roleLabel(assignment.role)}</TableCell>
                        <TableCell>
                          {current?.weekly_hours == null
                            ? "未登録（応援・スポット等）"
                            : `${current.weekly_hours}時間`}
                        </TableCell>
                        <TableCell>
                          {affiliation?.is_managing_pharmacist
                            ? "管理薬剤師"
                            : current
                              ? dutyLabel(current.duty)
                              : "未登録"}
                        </TableCell>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
              <Details>
                <Summary>店舗ごとの勤務条件の履歴</Summary>
                {props.conditions.map((affiliation) => (
                  <div key={`${affiliation.store_id}-${affiliation.starts_on}`}>
                    <Subheading>
                      {props.stores.find(
                        (store) => store.id === affiliation.store_id,
                      )?.name || affiliation.store_id}
                    </Subheading>
                    <Paragraph>
                      所属期間：{affiliation.starts_on} ～{" "}
                      {affiliation.ends_on || "継続中"}
                    </Paragraph>
                    {!affiliation.history.length ? (
                      <Paragraph>勤務条件の履歴はありません。</Paragraph>
                    ) : (
                      <Table>
                        <thead>
                          <tr>
                            <TableHeader>適用開始日</TableHeader>
                            <TableHeader>週勤務時間</TableHeader>
                            <TableHeader>従事区分</TableHeader>
                            <TableHeader>記録日時</TableHeader>
                            <TableHeader>記録者</TableHeader>
                          </tr>
                        </thead>
                        <tbody>
                          {affiliation.history.map((condition, index) => (
                            <tr key={index}>
                              <TableCell>{condition.effective_from}</TableCell>
                              <TableCell>
                                {condition.weekly_hours == null
                                  ? "未登録（応援・スポット等）"
                                  : `${condition.weekly_hours}時間`}
                              </TableCell>
                              <TableCell>{dutyLabel(condition.duty)}</TableCell>
                              <TableCell>
                                {new Date(condition.recorded_at).toLocaleString(
                                  "ja-JP",
                                  { timeZone: "Asia/Tokyo" },
                                )}
                              </TableCell>
                              <TableCell>{condition.recorded_by}</TableCell>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    )}
                  </div>
                ))}
              </Details>
            </>
          )}
        </>
      )}
    </Panel>
  );
}

function StoreSettingsForm({
  user,
  stores,
  conditions,
  onSave,
  onCancel,
  onSaved,
}: Props & { onCancel: () => void; onSaved: () => void }) {
  const [role, setRole] = useState(user.role);
  const [selectedIds, setSelectedIds] = useState(user.store_ids);
  const [roles, setRoles] = useState(
    Object.fromEntries(
      user.store_roles.map((item) => [item.store_id, item.role]),
    ),
  );
  const editableAffiliations = conditions.filter(
    (item) => !item.ends_on || item.ends_on >= todayInJapan(),
  );
  const current = editableAffiliations
    .map((item) => ({
      ...item,
      current:
        item.history
          .filter(
            (condition) =>
              condition.effective_from <=
              (item.starts_on > todayInJapan()
                ? item.starts_on
                : todayInJapan()),
          )
          .sort((a, b) => a.effective_from.localeCompare(b.effective_from))
          .at(-1) || null,
    }))
    .filter((item) => item.current);
  const [hours, setHours] = useState<Record<string, string>>(
    Object.fromEntries(
      current.map((item) => [item.store_id, item.current?.weekly_hours ?? ""]),
    ),
  );
  const [duties, setDuties] = useState<Record<string, string>>(
    Object.fromEntries(
      current.map((item) => [item.store_id, item.current!.duty]),
    ),
  );
  const [startsOn, setStartsOn] = useState<Record<string, string>>(
    Object.fromEntries(
      conditions
        .filter((item) => !item.ends_on || item.ends_on >= todayInJapan())
        .map((item) => [item.store_id, item.starts_on]),
    ),
  );
  const [effectiveDates, setEffectiveDates] = useState<Record<string, string>>(
    {},
  );
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const selected = stores.filter((store) => selectedIds.includes(store.id));
  const changes = selected.map((store) => ({
    store_id: store.id,
    starts_on: startsOn[store.id] || todayInJapan(),
    effective_from: conditions.some(
      (item) =>
        item.store_id === store.id &&
        (!item.ends_on || item.ends_on >= todayInJapan()),
    )
      ? effectiveDates[store.id] || todayInJapan()
      : startsOn[store.id] || todayInJapan(),
    weekly_hours: hours[store.id]?.trim() || null,
    duty: duties[store.id] || "other",
  }));
  const budget = assessStoreHoursBudget(
    user.staff?.weekly_contract_hours,
    changes,
    conditions,
    todayInJapan(),
  );
  return (
    <form
      onSubmit={async (event) => {
        event.preventDefault();
        if (pendingRef.current) return;
        setError(null);
        for (const store of selected) {
          const raw = (hours[store.id] || "").trim();
          if (raw && (!/^\d+(?:\.\d{1,2})?$/.test(raw) || Number(raw) > 168)) {
            setError(
              `${store.name}の週勤務時間は0～168、小数第2位までで入力してください。`,
            );
            return;
          }
        }
        if (budget.exceededOn) {
          setError(
            `店舗別の週勤務時間の合計（${budget.maximumHours}時間）が週所定労働時間（${user.staff?.weekly_contract_hours}時間）を超えています。適用日: ${budget.exceededOn}`,
          );
          return;
        }
        pendingRef.current = true;
        setPending(true);
        try {
          await onSave(
            role,
            selected.map((store) => ({
              store_id: store.id,
              role: roles[store.id] || "store_operator",
            })),
            user.staff_id ? changes : [],
          );
          onSaved();
        } catch (reason) {
          setError(
            reason instanceof Error
              ? reason.message
              : "店舗設定を保存できませんでした。",
          );
        } finally {
          pendingRef.current = false;
          setPending(false);
        }
      }}
    >
      {error && <Alert tone="error">{error}</Alert>}
      <SelectField
        label="ロール"
        value={role}
        onValueChange={setRole}
        disabled={pending}
        options={[
          { value: "corporate_admin", label: "法人管理者" },
          { value: "member", label: "一般ユーザー" },
        ]}
      />
      <Paragraph>
        ※ 保健所届出等に合わせた定常勤務の場合は週勤務時間を入力してください。当日の急な応援やスポット勤務の場合は、所属開始日に実際の勤務日（過去日付を指定した事後登録も可能）を指定し、週勤務時間は空欄（未登録）のままで登録できます。
      </Paragraph>
      <FieldGroup>
        <Subheading>所属店舗を選ぶ</Subheading>
        {stores.map((store) => (
          <Checkbox
            key={store.id}
            label={store.name}
            isSelected={selectedIds.includes(store.id)}
            disabled={pending}
            onChange={(checked) =>
              setSelectedIds((ids) =>
                checked
                  ? [...ids, store.id]
                  : ids.filter((id) => id !== store.id),
              )
            }
          />
        ))}
      </FieldGroup>
      {selected.map((store) => {
        const existing = conditions.find(
          (item) =>
            item.store_id === store.id &&
            (!item.ends_on || item.ends_on >= todayInJapan()),
        );
        return (
          <FieldGroup key={store.id}>
            <Subheading>{store.name}</Subheading>
            {user.staff_id && (
              <TextField
                name={`starts_${store.id}`}
                label={`${store.name}の所属開始日`}
                type="date"
                value={startsOn[store.id] || todayInJapan()}
                onValueChange={(value) =>
                  setStartsOn((values) => ({ ...values, [store.id]: value }))
                }
                required
                disabled={pending}
                readOnly={!!existing}
                description={
                  existing
                    ? "登録済みの所属開始日です。勤務条件の変更は下の適用開始日で指定します。"
                    : "当日の応援勤務や過去の応援の事後登録の場合は、実際の勤務開始日（過去日付も指定可能）を入力してください。"
                }
              />
            )}
            <SelectField
              label={`${store.name}の操作権限`}
              value={roles[store.id] || "store_operator"}
              onValueChange={(value) =>
                setRoles((values) => ({ ...values, [store.id]: value }))
              }
              disabled={pending}
              options={[
                { value: "store_operator", label: "編集可能" },
                { value: "store_viewer", label: "閲覧のみ" },
              ]}
            />
            {user.staff_id && (
              <>
                {existing && (
                  <TextField
                    name={`effective_${store.id}`}
                    label={`${store.name}の勤務条件の適用開始日`}
                    type="date"
                    value={effectiveDates[store.id] || todayInJapan()}
                    onValueChange={(value) =>
                      setEffectiveDates((values) => ({
                        ...values,
                        [store.id]: value,
                      }))
                    }
                    required
                    disabled={pending}
                  />
                )}
                <TextField
                  name={`hours_${store.id}`}
                  label={`${store.name}の週勤務時間（時間）`}
                  value={hours[store.id] || ""}
                  onValueChange={(value) =>
                    setHours((values) => ({ ...values, [store.id]: value }))
                  }
                  disabled={pending}
                  description="保健所届出等に合わせた定常勤務は0～168、小数第2位までで入力。急な応援・スポット勤務の場合は空欄（未登録）のままで構いません。"
                />
                <SelectField
                  label={`${store.name}の従事区分`}
                  value={duties[store.id] || "other"}
                  onValueChange={(value) =>
                    setDuties((values) => ({ ...values, [store.id]: value }))
                  }
                  disabled={pending}
                  options={dutyOptions}
                />
              </>
            )}
          </FieldGroup>
        );
      })}
      {!!selected.length && (
        <Paragraph>
          新規所属は店舗ごとの所属開始日から登録します。選択を外すと利用権限を解除します。勤務の所属終了や管理薬剤師の任命は専用操作で管理します。
        </Paragraph>
      )}
      {user.staff_id && (
        <Paragraph>
          登録済み週勤務時間の最大合計：{budget.maximumHours}時間 ／
          週所定労働時間：
          {user.staff?.weekly_contract_hours == null
            ? "未登録（上限未確認）"
            : `${user.staff.weekly_contract_hours}時間`}
          {budget.incomplete ? "（応援・スポット勤務等で勤務時間が未登録の店舗があります）" : ""}
        </Paragraph>
      )}
      <Row>
        <Button type="submit" disabled={pending}>
          所属・権限・勤務時間を保存する
        </Button>
        <Button variant="secondary" onAction={onCancel} disabled={pending}>
          キャンセル
        </Button>
      </Row>
    </form>
  );
}
