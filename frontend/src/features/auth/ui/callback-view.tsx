import { Entry, Heading, Paragraph } from "../../../shared/ui/layout/elements";
import { Alert } from "../../../shared/ui/feedback/alert";
import { Link } from "../../../shared/ui/navigation/link";
export function CallbackView({ error }: { error?: string }) {
  return (
    <Entry>
      <Heading>ログインの確認</Heading>
      {error ? (
        <Alert>{error}</Alert>
      ) : (
        <Paragraph role="status">確認中…</Paragraph>
      )}
      <Link href="/login">ログインへ戻る</Link>
    </Entry>
  );
}
