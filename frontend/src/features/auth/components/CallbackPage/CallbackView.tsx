import { Alert } from "../../../../shared/ui/Alert";
import { Entry, Heading, Paragraph } from "../../../../shared/ui/Elements";
import { Link } from "../../../../shared/ui/Link";

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
