import {
  Entry,
  Eyebrow,
  Heading,
  Paragraph,
  Notice,
} from "../../../shared/ui/layout/elements";
import type { Submission } from "../../../shared/forms/submission";
import { Link } from "../../../shared/ui/navigation/link";
import { Form } from "../../../shared/ui/controls/form";
import { TextField as Field } from "../../../shared/ui/controls/text-field";
export interface AcceptViewProps {
  secret: string;
  done: boolean;
  corporate: string | null;
  accepted: boolean;
  uncertain: boolean;
  loginSubmission: Submission;
  acceptanceSubmission: Submission;
  oidcAvailable: boolean;
  authenticated: boolean;
}
export function AcceptView({
  secret,
  done,
  corporate,
  accepted,
  loginSubmission,
  acceptanceSubmission,
  oidcAvailable,
  authenticated,
}: AcceptViewProps) {
  return (
    <Entry>
      <Eyebrow>INVITATION</Eyebrow>
      <Heading>{done ? "招待を受諾しました" : "法人への招待"}</Heading>
      {done ? (
        <>
          <Paragraph>ユーザー登録が完了しました。</Paragraph>
          {corporate ? (
            <Link
              href={`/admin/corporates/${encodeURIComponent(corporate)}`}
              appearance="action"
            >
              法人管理へ
            </Link>
          ) : (
            <Paragraph>
              店舗の利用権限を登録しました。業務画面は準備中です。
            </Paragraph>
          )}
        </>
      ) : (
        <>
          <Paragraph>
            招待先の本人としてログインしてから受諾してください。ログインで画面を離れた場合は、戻ってから招待URLの秘密を再入力してください。
          </Paragraph>
          {!authenticated && (
            <>
              {oidcAvailable ? (
                <Form
                  label="本人確認のためログイン"
                  {...loginSubmission}
                  onSubmit={loginSubmission.submit}
                />
              ) : (
                <Notice>
                  OIDC接続先が未設定です。管理者に設定を依頼してください。
                </Notice>
              )}
              {import.meta.env.DEV && (
                <Link href="/login?returnTo=%2Finvitations%2Faccept">
                  開発用トークンで接続
                </Link>
              )}
            </>
          )}
          <Form
            label={accepted ? "登録状態を確認する" : "招待を受諾する"}
            {...acceptanceSubmission}
            onSubmit={acceptanceSubmission.submit}
          >
            <Field
              name="secret"
              label="招待の秘密"
              type="password"
              required
              defaultValue={secret}
            />
          </Form>
          <Paragraph>
            利用できない招待は、発行した管理者へ確認してください。
          </Paragraph>
        </>
      )}
    </Entry>
  );
}
