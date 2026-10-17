# PharmacyDomain

薬局・調剤ドメインのAPIと管理画面。バックエンドは `backend/`、フロントエンドは `frontend/` に分けて管理する。

## 開発起動

1. ルートの `.env.example` を `.env` へコピーし、DB接続・ポートを設定する。
2. ルートで `pnpm db:up`。
3. ルートで `pnpm docker:build`、`pnpm db:migrate`、`pnpm db:seed` を順に実行する。ホストから直接Pythonを起動する場合はbackendで依存同期し、ルート.envのPOSTGRES_PORTを明示読込してホスト用DATABASE_URLを設定する。Compose内の接続先 `postgres:5432` とホスト用URLを混同しない。
4. seedが出力する `DEV_ACTOR_*` をルート.envへ設定する。`DEV_ACTOR_PRINCIPAL_ID=seed/vendor-admin` も必要。
5. ルートで `pnpm bootstrap` によりJS依存とPython依存を同期する。
6. ルートで `pnpm dev`。API（Docker Compose）とViteを同時起動する。`http://localhost:5173/admin` を開く。

APIだけなら `pnpm dev:backend`、フロントだけなら `pnpm dev:frontend`。ホストのPythonで直接APIを起動する場合は `pnpm dev:backend:local`（ルート.envのDATABASE_URLをホスト接続用に設定する）。

Viteの開発用ログイン画面で、DEV_ACTOR_TOKENと同じBearerトークンを入力する。固定トークンはメモリ内だけで保持し、再読込時は再接続する。API_PROXY_TARGETはルート.envで変更できる。未指定ならAPI_PORTを参照する。

法人一覧→法人登録→店舗登録→本人登録・ユーザー招待の順に操作できる。ユーザーは招待受諾後に一覧へ載る。店舗ロールにはスタッフ登録または既存スタッフの選択と本人紐付けが必要。招待URLは発行時にコピーし、宛先へ別途渡す（メール自動送信は行わない）。

固定トークン認証は招待受諾用の外部本人確認に対応していない。招待受諾の実利用には次のOIDC接続が必要。管理操作の開発用接続と、本番ログインを区別する。

## OIDCと本番配信

ルートの.env.exampleを参考に、VITE_OIDC_AUTHORITY、VITE_OIDC_CLIENT_ID、必要なVITE_OIDC_SCOPEを設定する。IdPにはSPAクライアントとしてAuthorization Code + PKCEを登録する。リダイレクト先はフロントのoriginに `/auth/callback`、ログアウト先は `/login`。APIのaudienceを持つaccess tokenが発行されるようIdP側の設定も合わせる。

backend側はOIDC_ISSUER・OIDC_AUDIENCE・OIDC_JWKS_URL等を設定し、`app.main:app` を起動する。初期ベンダーのexternal_subjectはIdPが返す `issuer/sub` と一致させる。秘密のclient_secretをVITE_変数へ置かない。VITE_変数は公開情報でビルドに埋め込まれる。

`pnpm docker:build` でイメージを作成できる。frontendはNginxで静的配信し、`/api/` をAPIへ転送、その他の深いURLをSPAへ戻す。Compose既定のapiは開発用起動点なので、本番ではcommandを `uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port 8000` に置き換え、OIDC環境変数を渡す。TLS終端は配備環境で用意する。IdP未設定の静的ビルドはログインできないため、ローカル固定トークンで触る場合はViteの開発サーバーを使う。

招待の受諾は `/invitations/accept`。ログインを往復すると招待秘密は保持しないので、復帰後に招待URLのfragmentに含まれる秘密を入力する。秘密はURLのquery、OIDC state、永続ストレージへ保存しない。

## 検証

すべてルートから操作する。`pnpm test` はバックエンドとフロントの単体テスト、`pnpm typecheck` / `pnpm lint` は両方を検査、`pnpm format:check` と `pnpm imports` はPythonの書式・依存契約を検査する。`pnpm build` はフロントのproduction build、`pnpm test:e2e` はブラウザーテスト。個別実行には `:backend` / `:frontend` 付きコマンドを使う。`pnpm check` はブラウザーテスト以外の検証とビルドをまとめて実行する。品質ゲートの正典はAGENTS.md。

ルートで `pnpm generate:api` を実行すると、実際のFastAPI OpenAPIからAPI型を再生成する。backendのuv環境が必要。型生成はDBへ接続しない。

`pnpm test:e2e` はAPIを制御したブラウザーテスト。実API確認用の `tests/e2e/real.spec.ts` はREAL_E2E_TOKENS（vendor/inviteeキーを持つJSONファイル）とE2E_BASE_URLを指定した専用環境でだけ実行する。テスト用サーバーは `backend/tests/browser_server.py` で、既存の署名JWT検証を使用するが鍵取得をテストダブルに置き換える。必ず専用一時DBを用意してマイグレーション・seedを済ませ、DATABASE_URLとREAL_E2E_TOKENSを設定し、ループバックでだけ起動する。本番では起動しない。実IdPとのログイン確認は別途必要。

設計の全体像は [docs/README.md](docs/README.md) を参照。
