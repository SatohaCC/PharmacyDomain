import { useState } from "react";
import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import {
  changeInitialPassword,
  selectStoreContext,
} from "../../../features/auth/api/local-authentication";
import { accessToken, setAccessToken } from "../../../features/auth/api/session";
import { StoreContextSelectorView } from "../../../features/stores/ui/store-context-selector-view";
import { Panel, Stack } from "../../../shared/ui/layout/panel";
import { Badge } from "../../../shared/ui/data-display/badge";
import {
  Heading,
  SectionHeading,
  Paragraph,
  ActionRow,
} from "../../../shared/ui/layout/elements";
import { Form } from "../../../shared/ui/controls/form";
import { TextField } from "../../../shared/ui/controls/text-field";
import { Alert } from "../../../shared/ui/feedback/alert";
import { errorText } from "../../../shared/api/errors";

export const Route = createFileRoute("/stores/$storeId/my-settings")({
  component: MySettingsPage,
});

function MySettingsPage() {
  const { storeId } = Route.useParams();
  const { actor, selectableStores, currentStore } = Route.useRouteContext();
  const router = useRouter();
  const navigate = useNavigate();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [switchingStore, setSwitchingStore] = useState(false);
  const [storeFeedback, setStoreFeedback] = useState<string | null>(null);
  const [storeError, setStoreError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSelectStore = async (targetStoreId: string) => {
    if (targetStoreId === storeId) return;
    setStoreFeedback(null);
    setStoreError(null);
    setSwitchingStore(true);
    try {
      const session = await selectStoreContext(targetStoreId);
      setAccessToken(session.access_token);
      await router.invalidate();
      const targetStore = selectableStores.find((s) => s.id === targetStoreId);
      setStoreFeedback(
        targetStore
          ? `表示店舗を「${targetStore.name}」に切り替えました。`
          : "表示店舗を切り替えました。",
      );
      await navigate({
        to: "/stores/$storeId/my-settings",
        params: { storeId: targetStoreId },
      });
    } catch (err: unknown) {
      setStoreError(errorText(err));
    } finally {
      setSwitchingStore(false);
    }
  };

  const handlePasswordChange = async () => {
    setFeedback(null);
    setErrorMessage(null);

    if (newPassword.length < 8) {
      setErrorMessage("新しいパスワードは8文字以上で入力してください。");
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMessage("確認用パスワードが一致しません。");
      return;
    }
    const token = accessToken();
    if (!token) {
      setErrorMessage("再ログインしてからお試しください。");
      return;
    }

    setSubmitting(true);
    try {
      const session = await changeInitialPassword(token, newPassword);
      setAccessToken(session.access_token);
      setNewPassword("");
      setConfirmPassword("");
      setFeedback("パスワードを変更しました。");
    } catch (err: unknown) {
      setErrorMessage(errorText(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Stack gap="normal">
      <Panel>
        <Heading>マイ設定</Heading>
        <Paragraph>ログイン中のアカウント情報とセキュリティ設定</Paragraph>
        <SectionHeading>アカウント情報</SectionHeading>
        <ActionRow>
          <span>ロール:</span>
          {actor.roles.map((r) => (
            <Badge key={r}>{r}</Badge>
          ))}
        </ActionRow>
        <Paragraph>
          選択中の店舗:{" "}
          {currentStore
            ? `${currentStore.name}（${currentStore.code}）`
            : "未選択"}
        </Paragraph>
        <Paragraph>スタッフID: {actor.staff_id ?? "未紐付け"}</Paragraph>

        <SectionHeading>表示店舗の切り替え</SectionHeading>
        {storeFeedback ? <Alert tone="info">{storeFeedback}</Alert> : null}
        {storeError ? <Alert tone="error">{storeError}</Alert> : null}
        {selectableStores.length > 0 ? (
          <StoreContextSelectorView
            stores={selectableStores}
            selectedStoreId={storeId}
            onSelectStore={(id) => void handleSelectStore(id)}
            disabled={switchingStore}
          />
        ) : (
          <Paragraph>切り替え可能な店舗はありません。</Paragraph>
        )}
      </Panel>

      <Panel>
        <SectionHeading>パスワード変更</SectionHeading>
        {feedback ? <Alert tone="info">{feedback}</Alert> : null}
        <Form
          onSubmit={() => void handlePasswordChange()}
          label={submitting ? "変更中..." : "パスワードを変更する"}
          pending={submitting}
          error={errorMessage ?? undefined}
        >
          <TextField
            name="new_password"
            label="新しいパスワード"
            type="password"
            value={newPassword}
            onValueChange={setNewPassword}
            required
          />
          <TextField
            name="confirm_password"
            label="新しいパスワード（確認）"
            type="password"
            value={confirmPassword}
            onValueChange={setConfirmPassword}
            required
          />
        </Form>
      </Panel>
    </Stack>
  );
}
