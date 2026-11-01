import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  Details,
  Summary,
} from "../../../shared/ui/layout/elements";
import {
  Table,
  TableHeader,
  TableCell,
} from "../../../shared/ui/data-display/table";
import { Badge } from "../../../shared/ui/data-display/badge";
import { Button } from "../../../shared/ui/controls/button";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
import { SelectField } from "../../../shared/ui/controls/select-field";
import { Checkbox } from "../../../shared/ui/controls/checkbox";
import { Alert } from "../../../shared/ui/feedback/alert";
import type { UserDetail } from "../model/user";
import {
  EMPLOYMENT_TYPE_LABELS,
  EMPLOYMENT_TYPE_OPTIONS,
  LEAVE_REASON_LABELS,
  LEAVE_REASON_OPTIONS,
} from "../model/registration";

const roleLabels: Record<string, string> = {
  corporate_admin: "法人管理者",
  store_operator: "店舗操作者",
  store_viewer: "店舗閲覧者",
};

export interface UserDetailViewProps {
  user: UserDetail;
  corporateId: string;
  availableStores: { id: string; name: string }[];
  onUpdateRole: (role: string, storeIds: string[]) => Promise<void>;
  onSuspend: () => Promise<void>;
  onReactivate: () => Promise<void>;
  onUpdateStaffNames?: (names: {
    last_name: string;
    first_name: string;
    last_name_kana: string;
    first_name_kana: string;
  }) => Promise<void>;
  onUpdateStaffJobTitle?: (jobTitle: string | null) => Promise<void>;
  onUpdateStaffEmployment?: (employment: {
    employment_type: string;
    weekly_contract_hours?: number | null;
  }) => Promise<void>;
  onStartStaffLeave?: (leave: {
    leave_reason: string;
    left_on: string;
  }) => Promise<void>;
  onReturnStaffFromLeave?: () => Promise<void>;
  statusMessage?: string | null;
  errorMessage?: string | null;
}

export function UserDetailView({
  user,
  availableStores,
  onUpdateRole,
  onSuspend,
  onReactivate,
  onUpdateStaffNames,
  onUpdateStaffJobTitle,
  onUpdateStaffEmployment,
  onStartStaffLeave,
  onReturnStaffFromLeave,
  statusMessage,
  errorMessage,
}: UserDetailViewProps) {
  const [role, setRole] = useState(user.role);
  const [selectedStoreIds, setSelectedStoreIds] = useState<string[]>(user.store_ids);
  const [roleEditing, setRoleEditing] = useState(false);
  const [staffEditing, setStaffEditing] = useState(false);
  const [employmentEditing, setEmploymentEditing] = useState(false);
  const [employmentType, setEmploymentType] = useState(
    user.staff?.employment_type || "regular",
  );
  const [leaveReason, setLeaveReason] = useState("childcare");
  const [leftOn, setLeftOn] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleToggleStore = (storeId: string) => {
    setSelectedStoreIds((prev) =>
      prev.includes(storeId)
        ? prev.filter((id) => id !== storeId)
        : [...prev, storeId],
    );
  };

  const handleRoleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onUpdateRole(role, selectedStoreIds);
      setRoleEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStaffSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onUpdateStaffNames) return;
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    try {
      await onUpdateStaffNames({
        last_name: String(fd.get("last_name") || ""),
        first_name: String(fd.get("first_name") || ""),
        last_name_kana: String(fd.get("last_name_kana") || ""),
        first_name_kana: String(fd.get("first_name_kana") || ""),
      });
      if (onUpdateStaffJobTitle) {
        await onUpdateStaffJobTitle(fd.get("job_title") ? String(fd.get("job_title")) : null);
      }
      setStaffEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEmploymentSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onUpdateStaffEmployment) return;
    setIsSubmitting(true);
    const fd = new FormData(e.currentTarget);
    const hours = fd.get("weekly_contract_hours")
      ? Number(fd.get("weekly_contract_hours"))
      : null;
    try {
      await onUpdateStaffEmployment({
        employment_type: employmentType,
        weekly_contract_hours: hours,
      });
      setEmploymentEditing(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartLeaveSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!onStartStaffLeave || !leftOn) return;
    setIsSubmitting(true);
    try {
      await onStartStaffLeave({
        leave_reason: leaveReason,
        left_on: leftOn,
      });
      setLeftOn("");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReturnFromLeave = async () => {
    if (!onReturnStaffFromLeave) return;
    setIsSubmitting(true);
    try {
      await onReturnStaffFromLeave();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async () => {
    setIsSubmitting(true);
    try {
      if (user.status === "active") {
        await onSuspend();
      } else {
        await onReactivate();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const assignedStoreNames = availableStores
    .filter((s) => user.store_ids.includes(s.id))
    .map((s) => s.name);

  return (
    <>
      {statusMessage && <Alert tone="info">{statusMessage}</Alert>}
      {errorMessage && <Alert tone="error">{errorMessage}</Alert>}

      <Panel>
        <Subheading>ユーザー詳細</Subheading>
        <Paragraph>
          本人ID: {user.person_id} ｜ 権限:{" "}
          <Badge>{roleLabels[user.role] || user.role}</Badge>
          法人アクセス:{" "}
          <Badge>{user.status === "active" ? "有効" : "停止中"}</Badge>
          アカウント:{" "}
          <Badge>{user.account_status === "active" ? "有効" : "停止中"}</Badge>
        </Paragraph>
      </Panel>

      <Panel>
        <Row>
          <SectionHeading>法人権限・所属店舗</SectionHeading>
          <Button
            variant="secondary"
            onAction={() => setRoleEditing(!roleEditing)}
            disabled={isSubmitting}
          >
            {roleEditing ? "キャンセル" : "権限を変更"}
          </Button>
        </Row>
        {roleEditing ? (
          <form onSubmit={(e) => void handleRoleSubmit(e)}>
            <SelectField
              name="role"
              label="ロール"
              value={role}
              onValueChange={(val: string) => setRole(val)}
              options={[
                { value: "corporate_admin", label: "法人管理者" },
                { value: "store_operator", label: "店舗操作者" },
                { value: "store_viewer", label: "店舗閲覧者" },
              ]}
            />
            <SectionHeading>利用可能店舗</SectionHeading>
            {availableStores.map((store) => (
              <Checkbox
                key={store.id}
                label={store.name}
                isSelected={selectedStoreIds.includes(store.id)}
                onChange={() => handleToggleStore(store.id)}
              />
            ))}
            <Row>
              <Button type="submit" disabled={isSubmitting}>保存する</Button>
            </Row>
          </form>
        ) : (
          <Table>
            <tbody>
              <tr>
                <TableHeader>ロール</TableHeader>
                <TableCell>{roleLabels[user.role] || user.role}</TableCell>
              </tr>
              <tr>
                <TableHeader>所属店舗</TableHeader>
                <TableCell>
                  {assignedStoreNames.length > 0
                    ? assignedStoreNames.join("、")
                    : "全店舗または未指定"}
                </TableCell>
              </tr>
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel>
        <SectionHeading>アカウント利用状態</SectionHeading>
        <Paragraph>
          法人内でのこのアカウントの利用停止または再開を切り替えます。
        </Paragraph>
        <Row>
          <Button
            variant="secondary"
            onAction={() => void handleToggleActive()}
            disabled={isSubmitting}
          >
            {user.status === "active" ? "法人利用を停止する" : "法人利用を再開する"}
          </Button>
        </Row>
      </Panel>

      {user.staff && (
        <Panel>
          <Row>
            <SectionHeading>スタッフ情報・労働契約</SectionHeading>
            {onUpdateStaffNames && (
              <Button
                variant="secondary"
                onAction={() => setStaffEditing(!staffEditing)}
                disabled={isSubmitting}
              >
                {staffEditing ? "キャンセル" : "編集"}
              </Button>
            )}
          </Row>
          {staffEditing ? (
            <form onSubmit={(e) => void handleStaffSubmit(e)}>
              <Field
                name="last_name"
                label="姓"
                defaultValue={user.staff.last_name}
                required
              />
              <Field
                name="first_name"
                label="名"
                defaultValue={user.staff.first_name}
                required
              />
              <Field
                name="last_name_kana"
                label="セイ"
                defaultValue={user.staff.last_name_kana}
                required
              />
              <Field
                name="first_name_kana"
                label="メイ"
                defaultValue={user.staff.first_name_kana}
                required
              />
              <Field
                name="job_title"
                label="役職"
                defaultValue={user.staff.job_title || ""}
              />
              <Row>
                <Button type="submit" disabled={isSubmitting}>保存する</Button>
              </Row>
            </form>
          ) : (
            <Table>
              <tbody>
                <tr>
                  <TableHeader>氏名</TableHeader>
                  <TableCell>
                    {user.staff.last_name} {user.staff.first_name}（
                    {user.staff.last_name_kana} {user.staff.first_name_kana}）
                  </TableCell>
                  <TableHeader>社員番号</TableHeader>
                  <TableCell>{user.staff.code || "未登録"}</TableCell>
                </tr>
                <tr>
                  <TableHeader>役職</TableHeader>
                  <TableCell>{user.staff.job_title || "未設定"}</TableCell>
                  <TableHeader>資格区分</TableHeader>
                  <TableCell>
                    {user.staff.is_pharmacist ? <Badge>薬剤師</Badge> : "スタッフ"}
                  </TableCell>
                </tr>
                <tr>
                  <TableHeader>雇用形態</TableHeader>
                  <TableCell>
                    {EMPLOYMENT_TYPE_LABELS[user.staff.employment_type] ||
                      user.staff.employment_type}
                  </TableCell>
                  <TableHeader>週所定労働時間</TableHeader>
                  <TableCell>
                    {user.staff.weekly_contract_hours !== null
                      ? `${user.staff.weekly_contract_hours} 時間`
                      : "未設定"}
                    {user.staff.effective_full_time_equivalent !== null && (
                      <Badge>常勤換算: {user.staff.effective_full_time_equivalent}</Badge>
                    )}
                  </TableCell>
                </tr>
                <tr>
                  <TableHeader>就業状態</TableHeader>
                  <TableCell colSpan={3}>
                    {user.staff.status === "on_leave" ? (
                      <Badge>休職中（{LEAVE_REASON_LABELS[user.staff.leave_reason || ""] || user.staff.leave_reason || "理由未設定"}）</Badge>
                    ) : (
                      <Badge>稼働中</Badge>
                    )}
                  </TableCell>
                </tr>
              </tbody>
            </Table>
          )}

          {onUpdateStaffEmployment && (
            <div style={{ marginTop: "1rem" }}>
              <Row>
                <SectionHeading>労働契約の変更</SectionHeading>
                <Button
                  variant="secondary"
                  onAction={() => setEmploymentEditing(!employmentEditing)}
                  disabled={isSubmitting}
                >
                  {employmentEditing ? "キャンセル" : "契約変更"}
                </Button>
              </Row>
              {employmentEditing && (
                <form onSubmit={(e) => void handleEmploymentSubmit(e)}>
                  <SelectField
                    name="employment_type"
                    label="雇用形態"
                    value={employmentType}
                    onValueChange={(val: string) => setEmploymentType(val)}
                    options={EMPLOYMENT_TYPE_OPTIONS}
                  />
                  <Field
                    name="weekly_contract_hours"
                    label="週所定労働時間"
                    defaultValue={user.staff.weekly_contract_hours !== null ? String(user.staff.weekly_contract_hours) : ""}
                    description="例: 40.0"
                  />
                  <Row>
                    <Button type="submit" disabled={isSubmitting}>契約内容を保存する</Button>
                  </Row>
                </form>
              )}
            </div>
          )}

          <div style={{ marginTop: "1rem" }}>
            <SectionHeading>休職・復職管理</SectionHeading>
            {user.staff.status === "on_leave" ? (
              <Row>
                <Paragraph>現在休職中です。</Paragraph>
                {onReturnStaffFromLeave && (
                  <Button onAction={() => void handleReturnFromLeave()} disabled={isSubmitting}>
                    休職から復職する
                  </Button>
                )}
              </Row>
            ) : (
              <Details>
                <Summary>休職手続きを開く</Summary>
                {onStartStaffLeave && (
                  <form onSubmit={(e) => void handleStartLeaveSubmit(e)} style={{ marginTop: "0.5rem" }}>
                    <SelectField
                      name="leave_reason"
                      label="休職理由"
                      value={leaveReason}
                      onValueChange={(val: string) => setLeaveReason(val)}
                      options={LEAVE_REASON_OPTIONS}
                    />
                    <Field
                      name="left_on"
                      label="休職開始日 (YYYY-MM-DD)"
                      value={leftOn}
                      onValueChange={(val: string) => setLeftOn(val)}
                      description="例: 2026-04-01"
                      required
                    />
                    <Row>
                      <Button type="submit" disabled={isSubmitting || !leftOn.trim()}>
                        休職を開始する
                      </Button>
                    </Row>
                  </form>
                )}
              </Details>
            )}
          </div>
        </Panel>
      )}
    </>
  );
}
