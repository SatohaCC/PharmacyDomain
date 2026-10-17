import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Form, Field, text } from "../shared/ui/common";
import { login, oidc, setAccessToken } from "../shared/auth/session";
import { safeReturnPath } from "../shared/api/client";
export const Route = createFileRoute("/login")({
  validateSearch: (s: Record<string, unknown>) => ({
    returnTo: safeReturnPath(s.returnTo),
  }),
  component: Login,
});
function Login() {
  const { returnTo } = Route.useSearch();
  const navigate = useNavigate();
  return (
    <main className="entry">
      <span className="eyebrow">PHARMACY DOMAIN</span>
      <h1>管理画面にログイン</h1>
      <p>法人・店舗・ユーザーを管理します。</p>
      {oidc() ? (
        <Form label="ログイン" onSubmit={() => login(returnTo)} />
      ) : (
        <p className="notice">
          認証接続先が未設定です。OIDCの環境変数を設定してください。
        </p>
      )}
      {import.meta.env.DEV && (
        <section>
          <h2>開発用の接続</h2>
          <p>
            取得済みBearerトークンをこの画面内だけで利用します。再読込すると消去されます。
          </p>
          <Form
            label="接続する"
            onSubmit={async (d) => {
              setAccessToken(text(d, "token"));
              await navigate({ href: returnTo });
            }}
          >
            <Field
              name="token"
              label="Bearerトークン"
              type="password"
              required
            />
          </Form>
        </section>
      )}
    </main>
  );
}
