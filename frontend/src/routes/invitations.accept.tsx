import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { api, result, readInvitation, ApiError } from "../shared/api/client";
import { accessToken, login, oidc } from "../shared/auth/session";
import { Form, Field, text } from "../shared/ui/common";
export const Route = createFileRoute("/invitations/accept")({
  component: Accept,
});
function Accept() {
  const [secret] = useState(readInvitation);
  const [done, setDone] = useState(false);
  const [corporate, setCorporate] = useState<string | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  return (
    <main className="entry">
      <span className="eyebrow">INVITATION</span>
      <h1>{done ? "招待を受諾しました" : "法人への招待"}</h1>
      {done ? (
        <>
          <p>ユーザー登録が完了しました。</p>
          {corporate ? (
            <Link
              className="button"
              to="/admin/corporates/$corporateId"
              params={{ corporateId: corporate }}
            >
              法人管理へ
            </Link>
          ) : (
            <p>店舗の利用権限を登録しました。業務画面は準備中です。</p>
          )}
        </>
      ) : (
        <>
          <p>
            招待先の本人としてログインしてから受諾してください。ログインで画面を離れた場合は、戻ってから招待URLの秘密を再入力してください。
          </p>
          {!accessToken() && (
            <>
              {oidc() ? (
                <Form
                  label="本人確認のためログイン"
                  onSubmit={() => login("/invitations/accept")}
                />
              ) : (
                <p className="notice">
                  OIDC接続先が未設定です。管理者に設定を依頼してください。
                </p>
              )}
              {import.meta.env.DEV && (
                <Link to="/login" search={{ returnTo: "/invitations/accept" }}>
                  開発用トークンで接続
                </Link>
              )}
            </>
          )}
          <Form
            label={accepted ? "登録状態を確認する" : "招待を受諾する"}
            onSubmit={async (d) => {
              if (uncertain)
                throw new Error(
                  "前回の結果が不明です。再ログインして利用権限と招待状態を管理者へ確認してください。",
                );
              if (!accessToken())
                throw new Error("先に本人確認のためログインしてください。");
              if (!accepted) {
                try {
                  await result(
                    api.POST("/user-invitations/acceptance", {
                      body: { secret: text(d, "secret") },
                    }),
                  );
                  setAccepted(true);
                } catch (error) {
                  if (error instanceof ApiError && error.uncertain)
                    setUncertain(true);
                  throw error;
                }
              }
              const actor = await result(api.GET("/me"));
              setCorporate(
                actor.roles.includes("corporate_admin")
                  ? actor.corporate_id
                  : null,
              );
              setDone(true);
            }}
          >
            <Field
              name="secret"
              label="招待の秘密"
              type="password"
              required
              defaultValue={secret}
            />
          </Form>
          <p>利用できない招待は、発行した管理者へ確認してください。</p>
        </>
      )}
    </main>
  );
}
