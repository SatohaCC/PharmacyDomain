import { useState } from "react";
import { Panel } from "../../../shared/ui/layout/panel";
import {
  Title,
  Subheading,
  SectionHeading,
  Paragraph,
  Row,
  FieldGroup,
} from "../../../shared/ui/layout/elements";
import { TextField } from "../../../shared/ui/controls/text-field";
import { Button } from "../../../shared/ui/controls/button";
import { Alert } from "../../../shared/ui/feedback/alert";
import type { UserLifecycleState } from "../model/lifecycle";

export interface UserLifecycleViewProps {
  user: UserLifecycleState;
  onRetire: (retiredOn: string) => Promise<void> | void;
  onActivateStaff?: () => Promise<void> | void;
  onReactivateAccount?: () => Promise<void> | void;
  onReactivateMembership?: () => Promise<void> | void;
  errorMessage?: string | null;
  isSubmitting?: boolean;
}

export function UserLifecycleView({
  user,
  onRetire,
  onActivateStaff,
  onReactivateAccount,
  onReactivateMembership,
  errorMessage,
  isSubmitting = false,
}: UserLifecycleViewProps) {
  const [retiredOn, setRetiredOn] = useState(
    user.retiredOn || new Date().toISOString().slice(0, 10),
  );

  const canRetire =
    user.isStaffActive &&
    user.accountStatus === "active" &&
    user.membershipStatus === "active";

  return (
    <Panel>
      <Title>
        <Subheading>ユーザー状態管理（退職・再雇用）</Subheading>
      </Title>
      <Paragraph>
        スタッフの退職および段階的な再雇用権限を管理します。
      </Paragraph>

      {errorMessage && <Alert tone="error">{errorMessage}</Alert>}

      <FieldGroup>
        <Paragraph>
          <strong>スタッフ氏名:</strong> {user.staffName}
        </Paragraph>
        <Paragraph>
          <strong>在籍状態:</strong>{" "}
          {user.isStaffActive ? "在籍中" : "退職済み"}
        </Paragraph>
        <Paragraph>
          <strong>アカウント状態:</strong>{" "}
          {user.accountStatus === "active" ? "有効" : "停止中"}
        </Paragraph>
        <Paragraph>
          <strong>法人権限:</strong>{" "}
          {user.membershipStatus === "active" ? "有効" : "停止中"}
        </Paragraph>
        {user.storeName && (
          <Paragraph>
            <strong>所属店舗:</strong> {user.storeName}
          </Paragraph>
        )}
      </FieldGroup>

      {canRetire ? (
        <FieldGroup>
          <SectionHeading>退職処理</SectionHeading>
          <Paragraph>
            退職日を指定して退職処理を実行します。在任中の管理薬剤師は任命終了または交代が必要です。
          </Paragraph>
          <Row>
            <TextField
              name="retired_on"
              label="退職日"
              type="date"
              value={retiredOn}
              onValueChange={setRetiredOn}
            />
            <Button
              variant="secondary"
              disabled={isSubmitting || !retiredOn}
              onAction={() => onRetire(retiredOn)}
            >
              {isSubmitting ? "処理中..." : "退職処理を実行"}
            </Button>
          </Row>
        </FieldGroup>
      ) : (
        <FieldGroup>
          <SectionHeading>段階的再雇用・再開</SectionHeading>
          <Paragraph>
            退職者の復職では、スタッフ再開、所属店舗設定、アカウント再開、法人権限再付与を段階的に実行します。
          </Paragraph>
          <FieldGroup>
            <Row>
              <Paragraph>1. スタッフ状態:</Paragraph>
              {user.isStaffActive ? (
                <Paragraph>再開済み（在籍中）</Paragraph>
              ) : (
                <Button
                  variant="primary"
                  disabled={isSubmitting}
                  onAction={onActivateStaff}
                >
                  スタッフを再開
                </Button>
              )}
            </Row>
            <Row>
              <Paragraph>2. アカウント状態:</Paragraph>
              {user.accountStatus === "active" ? (
                <Paragraph>有効</Paragraph>
              ) : (
                <Button
                  variant="primary"
                  disabled={isSubmitting || !user.isStaffActive}
                  onAction={onReactivateAccount}
                >
                  アカウントを再開
                </Button>
              )}
            </Row>
            <Row>
              <Paragraph>3. 法人権限状態:</Paragraph>
              {user.membershipStatus === "active" ? (
                <Paragraph>有効</Paragraph>
              ) : (
                <Button
                  variant="primary"
                  disabled={
                    isSubmitting ||
                    !user.isStaffActive ||
                    user.accountStatus !== "active"
                  }
                  onAction={onReactivateMembership}
                >
                  法人権限を再開
                </Button>
              )}
            </Row>
          </FieldGroup>
        </FieldGroup>
      )}
    </Panel>
  );
}
