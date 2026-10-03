# AGENTS.md

薬局・調剤ドメイン（マルチテナント法人 / 店舗 / スタッフ）のオニオンアーキテクチャ開発ルール。

## コマンド & 品質ゲート

```bash
uv sync --locked                 # 依存同期
uv run pytest -q                 # 全テスト実行（アーキテクチャ規則の検証を含む）
uv run mypy app tests tools      # 型チェック (strict = true)
uv run ruff check . && uv run ruff format --check .  # Lint & Format チェック

# 実PostgreSQLに対する結合テスト（TEST_DATABASE_URL が無ければ自動スキップ）
docker compose up -d postgres
set -a; [ -f .env ] && . ./.env; set +a  # シェルは.envを自動で読まないので明示的に読み込む
TEST_DATABASE_URL=postgresql+asyncpg://pharmacydomain:pharmacydomain-dev-password@127.0.0.1:${POSTGRES_PORT:-5432}/pharmacydomain \
  uv run pytest -m integration -q

# 個別実行（違反箇所を特定したいとき）
uv run python -m tools.check_imports --verbose --fail-on-violation  # 依存の向き
uv run python -m tools.check_lcom --verbose --fail-on-violation     # クラス凝集度
uv run python -m tools.check_fake_conformance --verbose --fail-on-violation  # フェイクのProtocol適合
```

- **結合テストの接続ポートは `POSTGRES_PORT` から引く**: `compose.yaml` はホスト側の公開ポートを `.env` の `POSTGRES_PORT`（既定 5432）に従わせている。コマンド例で `5432` をベタ書きすると、`POSTGRES_PORT` を変えている環境（他プロジェクトとの衝突回避等）でこのコマンドをそのまま実行したときに接続エラーになる。`TEST_DATABASE_URL` が無いときの自動スキップと違い、間違ったポートへの接続は `ConnectionRefusedError` として失敗するので気づけはするが、そこで手が止まる。**シェルは `.env` を自動で読み込まない**（読むのは `docker compose` 自身だけ）ので、`${POSTGRES_PORT:-5432}` と書くだけでは足りず、`TEST_DATABASE_URL=...` を組み立てる前にコマンド例の側で `.env` を読み込む必要がある。読み込まなければ環境変数 `POSTGRES_PORT` は未設定のままなので既定値 5432 に落ち、`.env` で上書きしている環境では書いた本人の意図に反してベタ書きと同じ結果になる。
- **言語・コメント**: ドキュメント、docstring、エラーメッセージ、テスト名はすべて**日本語**。
- **品質要求**: `mypy --strict` と `ruff` のチェックを必ずパスさせること。
- **CI**: 上記5つのゲートは `.github/workflows/quality-gate.yml` が `main` への push と全 pull request で実行する。結合テストは PostgreSQL サービスを持つ別ジョブで走る。ゲートを増減するときは、このファイル・本節のコマンド一覧・`tests/tools/test_ci_quality_gate.py` の `REQUIRED_GATES` の3つを揃えないと pytest が落ちる。**ブランチ保護は未設定なので、赤いまま `main` へ push すること自体は止まらない**（GitHubのリポジトリ設定でしか変えられず、リポジトリ内のファイルからは強制できない）。
- **パッケージ構成**: `app/` `tests/` `tools/` 配下で `.py` を持つディレクトリには必ず `__init__.py` を置く。名前空間パッケージのままだと、(1) そのディレクトリだけを指定して `pytest` を回したときにルートが `sys.path` に入らず `app` を import できない、(2) 別ディレクトリに同名モジュールを置いた瞬間にトップレベル名が衝突して収集が壊れる。`tests/tools/test_package_layout.py` が強制する。
- **package initializerは空にする**: `app/`・`tests/`・`tools/`・`migrations/` の `__init__.py` は空またはモジュールドキュメント文字列だけにする。公開名を再エクスポートせず、利用側はクラス・関数・Protocolを定義元モジュールからimportする。新しいUseCaseを追加しても `__init__.py` の `__all__` は更新しない。initializerの実行文禁止はpackage layoutテスト、`app/` の明示import循環は `tools/check_imports.py` が検査する。
- **結合テストの分離**: 実DBを要するテストは `tests/integration/` に置き、`TEST_DATABASE_URL` が無ければ自動でスキップする。スキップは「実行したが何も確かめていない」状態なので、CIでは必ずDBを与える専用ジョブで `-m integration` を走らせる。マーカーは `tests/integration/conftest.py` が自動で付ける（各モジュールで付け忘れると、DBの無いジョブ側へ紛れ込む）。
- **アーキテクチャ規則**: 依存の向き・凝集度・フェイクのProtocol適合は `tools/` の静的チェッカが強制する。設定は `pyproject.toml` の `[tool.import_rules]` / `[tool.lcom]` / `[tool.fake_rules]`、実行は `tests/tools/test_architecture_rules.py` 経由で `pytest` に含まれる。設計ルールを追加するときは、文章だけでなくチェッカの設定にも反映する。

## レイヤー別ルール（DDD & オニオンアーキテクチャ）

各レイヤーの詳細ルールは `.agents/rules/` 配下のファイルに分割管理されています。

- **[Domain層ルール (.agents/rules/domain.md)](.agents/rules/domain.md)**:
  最内周の業務ロジック。エンティティ・集約の不変性、Domain Primitive、Domain Service、ライフサイクル表現、各コンテキスト（組織・保険受付請求・臨床調剤）の不変条件。
- **[Application層ルール (.agents/rules/application.md)](.agents/rules/application.md)**:
  ユースケース・業務オーケストレーション。コンテキスト間依存規則、CorporateAccessService、店舗ロール二重防御、保存前ガード（CompositeWriteGuard / OrganizationLock）、DTO・入力正規化、ユースケース追加手順。
- **[Infrastructure層ルール (.agents/rules/infrastructure.md)](.agents/rules/infrastructure.md)**:
  永続化とDI配線。PostgreSQLアダプタ構成、JSONB 1行1集約、列導出、楽観ロック、Unit of Work、排他制約（daterange / gist）、DI束構成。
- **[Presentation層ルール (.agents/rules/presentation.md)](.agents/rules/presentation.md)**:
  HTTP境界（FastAPI）。ルータ構成、共通エラー翻訳（ErrorResponse / errors.py）、認証窓口、OpenAPIスキーマ、リクエスト/レスポンスモデル規約、dev_main.py。

## 横断アーキテクチャ & 設計ルール

- **正典の分担**: プロジェクト目的と全体像は [docs/README.md](docs/README.md)、重要な設計判断と理由は [docs/decisions.md](docs/decisions.md)、外部根拠と未解決事項は対応する `docs/ddd/` 文書に置く。現在の型と振る舞いは `app/`、実行可能な保証は `tests/` と `tools/`、実装手順と品質ゲートは本ファイルを正典とする。`docs/reports/` は確認日つきのスナップショットで、後から更新しない（更新すると、その日に何が出来ていたかを指せる文書が無くなる）。
- **文書とコードの分離**: コードと通常テストは `docs/` のパス・見出し・ADR番号・文書用の不変条件IDを参照しない。必要な理由は、その箇所だけで理解できる語彙でdocstringやテスト名に書く。文書にはクラス・フィールド・テスト・不変条件の網羅表を複製せず、目的、境界、採否の理由、一次資料の解釈、未解決事項が変わるときだけ更新する。`tests/tools/test_docs_decoupling.py` は、文書を指すことが構文だけで確定する3形式（パス・ADR番号・不変条件ID）を検出して強制する。見出し名は改名・削除後の古い参照を判定できず、普通のドメイン語彙とも衝突するため、機械検査の対象にしない。
- **依存の向き**: 外 → 内（`app/domain/` は FastAPI, DB, `app/application/` に一切非依存）。`tools/check_imports.py` が強制する。**フレームワークの禁止をDomainで止めない**。`app/application/` も `fastapi` / `sqlalchemy` を直接 import できず、`app/presentational/` は `sqlalchemy` を触れない（`fastapi` はHTTP境界そのものなので禁じない）。Domainだけを守っても、ユースケースが `AsyncSession` や `Request` を引数で受け取れる限り「具体的なアダプタは Composition Root から Protocol へ接続する」という前提は静かに崩れるし、ルータが `commit` を掴めればトランザクション境界が2箇所になる。
- **共通コードの配置**: Domainモデリング基盤は `app/domain/foundation/`、所有者のいない語彙と複数コンテキストで共有する規則は `app/domain/shared/`、Application層の共通処理は `app/application/common/` に置く。DDDのShared KernelはDomain語彙だけを指し、Application共通処理をShared Kernelと呼ばない。`foundation` は標準ライブラリだけ、`shared` は `foundation` だけ、`application/common` は標準ライブラリだけに依存させる。新しいコンテキストを追加するときは `[tool.import_rules.forbidden]` の3パッケージの禁止先と対応する設定テストも更新する。
- **テナント境界**: コンテキストは `corporate` / `store` / `staff` / `patient` / `coverage` / `reception` / `care_event` / `claim` / `prescription` / `dispensing` / `medication_history` / `medicine_catalog` / `identity` の13。集約間は **ID 参照のみ**（他集約のエンティティを直接保持しない）。他テナントデータへのアクセスは 403 ではなく 404（`XxxNotFoundError` または `TenantBoundaryNotFoundError`）として隠蔽する。
- **認証・認可境界**: 認証基盤が生成した信頼済み `ActorContext` をApplication層へ渡し、Command / Queryの対象 `corporate_id` と分離する。ベンダーシステム管理者は全法人、法人管理者は `ActorContext.corporate_id` と一致する自法人だけを操作できる。HTTP入力から `ActorContext` を組み立てない。
- **本人・アカウント・法人アクセス権の分離**: `AccountPerson`（法人所属が変わっても維持される人）/ `UserAccount`（本人に帰属し、外部の本人確認基盤の主体と1対1）/ `CorporateMembership`（ある法人での権限と店舗範囲）の3集約に分ける。スタッフとの対応は `StaffPersonLink` を独立集約とし、別人への付け替えはDBのトリガと複合外部キーで封じる（アプリ側の分岐で守ると、通らない経路が1つできた時点で壊れる）。`UserAccount.external_subject` は必ず固定する。本人確認境界が返すのは外部主体（`VerifiedSubject`）だけで、内部の本人は `ResolveActorUseCase` が `get_by_subject()` から引く。外部の認証基盤は自分が発行した主体しか知らないので、本人IDを受け取れる形にすると、テストのダブルだけが埋められる経路が型の上に残る。この順序なら未固定のアカウントは検索の時点で到達できない（`=` はNULLに当たらない）ので、「未固定だけ照合が効かない」状態を分岐で防がなくてよい。

## テスト指針

- AAA パターン（`Arrange` / `Act` / `Assert`）。
- **Domain モデルをモックしない**。実オブジェクトと `tests/fakes/` のインメモリ Repository を使用。
- テスト名は `test_<対象>_<条件>_<期待結果>`。

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.
詳細は [.agents/rules/graphify.md](.agents/rules/graphify.md) を参照。
