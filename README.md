# PharmacyDomain

薬局・調剤業務を、データベースやWebフレームワークから独立した純粋なドメインモデルとして再現するPythonプロジェクトです。
DDD（ドメイン駆動設計）とオニオンアーキテクチャを用い、業務上の不変条件を型、集約、Domain Service、Repository契約、網羅的なテストで保護します。

本プロジェクトの中心（コアドメイン）は、**「電子薬歴（服薬指導・薬学的管理指導）」および付随する調剤事実記録・患者医療プロファイル**です。

- 全体像・対象範囲・未解決事項: [docs/README.md](docs/README.md)
- 重要な設計判断と理由: [docs/decisions.md](docs/decisions.md)
- 開発規約と品質ゲート: [AGENTS.md](AGENTS.md)

現在の振る舞いは `app/`、実行可能な保証は `tests/` と `tools/` を正典とします。
`docs/` はコードのAPI一覧ではなく、境界、判断理由、一次資料の解釈、未解決事項だけを扱います。

## システム概要とコアドメイン

調剤薬局における実務は、大きく**「レセコン（医事会計・レセプト請求システム）」**と**「電子薬歴・調剤システム（本ドメインのコア）」**の2つの独立したシステム領域に大別されます。
本プロジェクトは後者をコアドメインとしてモデル化しており、レセコンの排他的責務である調剤報酬点数の算定判定、窓口一部負担金計算、公費上限額管理票記帳、レセプト作成はドメイン外の関心事として厳格に分離しています（[docs/decisions.md](docs/decisions.md) の ADR-49, ADR-58）。

### 1. レセコンとの責務分担とデータ連携
- **レセコン（上流・外部システム）**:
  患者窓口受付、処方受領・入力、保険証・受給者証確認、調剤基本料・各種加算の算定判定、窓口負担金計算、公費上限額管理、レセプト（診療報酬明細書）作成およびオンライン請求。
- **外部データ連携（NSIPS等）**:
  窓口受付および処方入力が完了した段階で、NSIPS（新調剤システム情報交換仕様）等を介して処方・調剤セッション情報（分割調剤理由・回数・調製法などを含む）が本システムへ連携されます。
- **本システム（電子薬歴・調剤ドメイン）**:
  連携された「受付NSIPS単位」で客観的調剤セッション（`DispensingProcess`）を開始・鑑査し、薬剤師法第25条の2に基づく服薬指導記録（SOAP、残薬確認、手帳確認）や調剤後フォローアップ、トレーシングレポート（医師フィードバック）を含む薬歴（`MedicationHistoryRecord`）を記録・完結させます。確定した薬歴から患者医療プロファイル（アレルギー、副作用、既往歴、生活背景等の頭書き）が決定的に再構築・時系列投影されます。

### 2. 業務データフロー

```mermaid
flowchart LR
    subgraph Upstream [外部 / レセコン]
        R1[処方受付・患者情報入力] --> R2[NSIPSデータ出力]
    end

    subgraph CoreDomain [電子薬歴・調剤ドメイン]
        R2 --> D1[調剤セッション開始<br>DispensingProcess]
        D1 --> D2[調剤鑑査<br>監査事実記録]
        D2 --> M1[服薬指導・薬歴記録<br>MedicationHistoryRecord]
        M1 --> M2[確定薬歴]
        M2 --> P1[頭書きプロファイル投影<br>アレルギー・副作用・既往歴]
        M2 --> F1[服薬フォローアップ]
        M2 --> T1[トレーシングレポート<br>服薬情報等提供・医師FB]
    end
```

## コンテキストマップ

本プロジェクトは以下の12コンテキストで構成され、DDDの戦略的分類に基づき明確な責務境界を持ちます。集約間は **ID 参照のみ** で結合し、他集約のエンティティを直接保持しません。

### コアドメイン（Core Domain）
- **`MedicationHistory`（薬歴）**:
  薬剤師法第25条の2に基づく服薬指導記録（SOAP記録、残薬確認、手帳確認）、薬剤師法第28条の調剤録要件充足検証、調剤後服薬フォローアップ、処方医への服薬情報等提供（トレーシングレポート）と医師フィードバック、確定薬歴からの患者医療プロファイル（頭書き）時系列投影。
- **`Dispensing`（調剤）**:
  1回ごとの調剤セッション事実記録、変更調剤（代替調剤・数量調整・調製方法）、調剤鑑査（調剤者・鑑査者の記録）、処方箋原本との整合性検証。
- **`Prescription`（処方箋）**:
  処方箋原本の保持、医師疑義照会履歴（薬剤師法第23条）、後発医薬品への変更不可指示の管理。原本は法的証跡として確定後の改変を禁止。
- **`Patient`（患者）**:
  患者の同一性、外部患者ID、基本属性、患者ライフサイクル（有効・無効・非破壊的名寄せ統合）。

### 支援・汎用サブドメイン（Supporting / Generic Subdomain）
- **`Corporate`（法人）**:
  マルチテナント法人の同一性、名称、ライフサイクル状態（有効・休止）。
- **`Store`（店舗）**:
  法人配下の店舗、保険薬局情報、週次・特例開局時間（`OPEN` / `CLOSED` / `UNKNOWN` 3値判定）、管理薬剤師の配置義務（薬機法第7条第1項・業務日在任）と専任義務（薬機法第7条第3項・自然人単位）、閉局取消（訂正としての休止復帰）。
- **`Staff`（スタッフ）**:
  法人内スタッフ、保有資格（薬剤師・登録販売者等）、店舗所属履歴（主所属・兼務期間の非重複保証、退職日連動）。
- **`Identity`（認証・認可基盤）**:
  自然人（本人 `AccountPerson`）、外部IdPの主体と1対1に紐づく個人アカウント（`UserAccount`）、法人アクセス権（`CorporateMembership`）、招待受諾。
- **`MedicineCatalog`（医薬品マスタ）**:
  法人に属さない、時点付き医薬品参照マスタ（HOTコード・薬価基準等）。

### 外部境界・連携サブドメイン（Upstream / External Boundary）
- **`Coverage`（患者資格）**:
  レセコン等から連携される患者保険資格の台帳と有効期間。
- **`Reception`（受付）**:
  受付時に選択された資格履歴の受容。
- **`Claim`（請求）**:
  請求へ固定する資格スナップショット（現時点ではDomain層のみ）。

## アーキテクチャと設計方針

- **オニオンアーキテクチャ & 外 → 内の依存**:
  Domain層（`app/domain/`）はデータベースやWebフレームワーク（FastAPI, SQLAlchemy等）に一切依存しません。Application層（`app/application/`）が認可、入力変換、境界参照プロトコル、保存順序を調整します。
- **不変条件の多重防御**:
  単一集約内の不変条件はエンティティの生成・状態変更メソッド（frozen dataclass）で保護し、複数集約に跨る検証はDomain Serviceが担当します。
- **テナント・認可境界の二重防御**:
  他テナントデータへのアクセスは403ではなく404で隠蔽します。店舗ロール（`STORE_OPERATOR` / `STORE_VIEWER`）は権限表とSQLの取得条件（`RepositoryReadScope`）の両方で絞り込みます。
- **追記型監査と本人特定**:
  すべての更新はトランザクション内で監査ログを追記し、本人（自然人）と個人アカウントが特定されない更新は保存境界（`CompositeWriteGuard`）で拒否します。
- **現在形の保証**:
  Domain/Applicationモデルの全コンテキスト、およびClaimを除く永続化対象コンテキストの PostgreSQL Repositoryを実装済みです。HTTPルートは全コンテキストのユースケースを公開しています。外部IdPが発行したJWTを検証する本番認証基盤も実装済みで、`OIDC_*` を設定しない間は業務操作を401で拒否します。

## PostgreSQL 開発環境

`.env.example` を `.env` へコピーし、`docker compose up -d postgres` で PostgreSQL を起動します。
スキーマは `alembic upgrade head` で適用できます。API コンテナも起動する場合は `docker compose up -d` を使ってください。実運用の接続文字列・資格情報は Secret 管理へ置きます。

## 開発用の初期データ（シード）

```bash
export DATABASE_URL=postgresql+asyncpg://pharmacydomain:pharmacydomain-dev-password@127.0.0.1:5432/pharmacydomain
uv run python -m tools.seed_dev_data
```

法人・店舗・スタッフに加えて、**操作に必要な本人とアカウント**、スタッフとの対応、法人アクセス権、管理薬剤師の任命までを投入します。更新は監査の追記を伴い、監査行は `user_accounts` への複合外部キーを持つため、実在する本人とアカウントが無いと開発用の起動点は起動できても最初の更新で落ちます。

IDは固定で、投入の前に必ず読みます。**何度流しても行は増えず、既存の行は上書きしません**（手で変えた開発用データをシードが黙って戻さないため）。作り直したいときはテーブルを空にしてから流してください。シードは業務操作ではないので監査行は作りません。

実行すると `DEV_ACTOR_PERSON_ID` などを `.env` へ貼れる形で出力します。そのまま `.env` へ写せば、次節の開発用起動点がその主体で動きます。

## API を手元で試す

本番の起動点 `app.main:app` は、`OIDC_*` を設定しない限り業務操作をすべて401で拒否します（設定項目は [.env.example](.env.example) を参照してください）。
`docker compose` の api サービスは開発専用の起動点 `app.presentational.dev_main:create_dev_app` を起動し、`DEV_ACTOR_TOKEN`（既定 `dev-actor-token`）1つを固定の操作主体として通します。

<http://localhost:8000/docs> の Authorize にそのトークンを入れると、各エンドポイント（調剤セッション登録、薬歴記録、処方箋登録、患者情報など）を実行できます。既定の主体はベンダーシステム管理者で、`DEV_ACTOR_ROLE=corporate_admin` と `DEV_ACTOR_CORPORATE_ID` を与えると法人管理者に切り替わります。

`DEV_ACTOR_PERSON_ID` と `DEV_ACTOR_ACCOUNT_ID` は**必須**で、既定値はありません。前節のシードが出力した値を使ってください。未設定なら起動しません（存在しない行を指したまま起動して最初の更新で落ちるより早く止めます）。

開発用の起動点は `compose.yaml` からしか呼びません。本番イメージの `CMD` は `app.main:app` のままで、テストがその取り違えを検出します。

## 結合テスト

結合テストは PostgreSQL が必要です。`docker compose up -d postgres` で起動し、`TEST_DATABASE_URL` を与えて `uv run pytest -m integration -q` を実行します。
環境変数が無いときは自動でスキップされるので、DBが無くても `uv run pytest -q` は通ります。

## 永続化アーキテクチャ

PostgreSQL Repository は Claim（現時点では Domain 層のみ）を除く永続化対象コンテキストの集約を網羅しています。集約の JSONB payload と検索・一意性用の列を同一行へ保存し、保存は `ON CONFLICT` の1文で原子的に行い、行の世代（`version`）で後勝ちの上書きを拒否します。期間の重なりを禁じる不変条件（患者資格・医薬品マスタ・管理薬剤師専任）は排他制約で守ります。

## 品質ゲート

開発規約に従い、以下の品質ゲートがすべてパスすることを保証しています：

```bash
uv sync --locked                 # 依存同期
uv run pytest -q                 # 全テスト実行（2,300件超、アーキテクチャ規則検証含む）
uv run mypy app tests tools      # 型チェック (strict = true)
uv run ruff check . && uv run ruff format --check .  # Lint & Format チェック

# 個別アーキテクチャチェッカ
uv run python -m tools.check_imports --verbose --fail-on-violation  # 依存の向き
uv run python -m tools.check_lcom --verbose --fail-on-violation     # クラス凝集度
uv run python -m tools.check_fake_conformance --verbose --fail-on-violation  # Fake適合性
```
