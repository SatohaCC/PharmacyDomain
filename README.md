# PharmacyDomain

薬局ドメインを、データベースやWebフレームワークから独立したドメインモデルとして再現するPythonプロジェクトです。
DDDとオニオンアーキテクチャを用い、業務上の不変条件を型、集約、Domain Service、Repository契約、テストで保護します。

現在は法人・店舗・スタッフ・患者・資格・受付・請求・処方箋・調剤・薬歴・医薬品カタログの
Domain/Applicationモデルと、Claimを除く永続化対象コンテキストの PostgreSQL Repositoryを
実装済みです。HTTPルートは全コンテキストのユースケースを公開しています。認証基盤と
薬価基準等の実データ取り込みは未実装で、認証基盤が未接続の間、業務操作は401で拒否されます。

- 全体像・対象範囲・未解決事項: [docs/README.md](docs/README.md)
- 重要な設計判断と理由: [docs/decisions.md](docs/decisions.md)
- 開発規約と品質ゲート: [AGENTS.md](AGENTS.md)

現在の振る舞いは `app/`、実行可能な保証は `tests/` と `tools/` を正とします。
`docs/` はコードのAPI一覧ではなく、境界、判断理由、一次資料の解釈、未解決事項だけを扱います。

## PostgreSQL 開発環境

`.env.example` を `.env` へコピーし、`docker compose up -d postgres` で PostgreSQL を起動します。
スキーマは `alembic upgrade head` で適用できます。API コンテナも起動する場合は
`docker compose up -d` を使ってください。実運用の接続文字列・資格情報は Secret 管理へ置きます。

## API を手元で試す

認証基盤が未実装のため、本番の起動点 `app.main:app` は業務操作をすべて401で拒否します。
`docker compose` の api サービスは開発専用の起動点 `app.presentational.dev_main:create_dev_app`
を起動し、`DEV_ACTOR_TOKEN`（既定 `dev-actor-token`）1つを固定の操作主体として通します。

<http://localhost:8000/docs> の Authorize にそのトークンを入れると、各エンドポイントを
実行できます。既定の主体はベンダーシステム管理者で、`DEV_ACTOR_ROLE=corporate_admin` と
`DEV_ACTOR_CORPORATE_ID` を与えると法人管理者に切り替わります。

開発用の起動点は `compose.yaml` からしか呼びません。本番イメージの `CMD` は
`app.main:app` のままで、テストがその取り違えを検出します。

結合テストは PostgreSQL が必要です。`docker compose up -d postgres` で起動し、
`TEST_DATABASE_URL` を与えて `uv run pytest -m integration -q` を実行します。
環境変数が無いときは自動でスキップされるので、DBが無くても `uv run pytest -q` は通ります。

PostgreSQL Repository は Claim（現時点では Domain 層のみ）を除く永続化対象コンテキストの集約を網羅しています。集約の JSONB payload と
検索・一意性用の列を同一行へ保存し、保存は `ON CONFLICT` の1文で原子的に行い、
行の世代（`version`）で後勝ちの上書きを拒否します。期間の重なりを禁じる不変条件
（患者資格・医薬品マスタ）は排他制約で守ります。認証基盤の実装は後続作業です。
