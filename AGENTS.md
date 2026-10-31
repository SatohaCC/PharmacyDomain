# AGENTS.md

薬局・調剤ドメインをDDD・オニオンアーキテクチャで開発するための入口。

## 共通の約束

- Pythonのソース・テスト・ツール・設定は`backend/`配下に置く。通常コマンドはリポジトリルートからpnpmで実行し、Pythonの実行・依存解決はbackendのuvへ委譲する。
- ドキュメント、docstring、エラーメッセージ、テスト名は日本語にする。
- 開発中のため後方互換性は要求しない。明示依頼がなければ、旧仕様だけの互換処理・別名・フォールバックを残さず、利用側・設定・テスト・通常文書も新契約へ揃える。
- Domainモデルは実オブジェクトでテストする。インメモリRepositoryは`backend/tests/fakes/`を使い、AAAと`test_<対象>_<条件>_<期待結果>`に従う。
- 現在の型・振る舞いはコード、実行可能な保証はテスト・検査器・設定を正とする。コードと通常テストは文書パス・ADR番号・文書用不変条件IDへ依存せず、理由をその場で理解できる言葉で書く。

## 必要な資料だけを読む

作業開始時に次の条件で参照先を選ぶ。複数の境界を変更する場合だけ、該当する行を追加で読む。

| 作業 | 入口 |
| --- | --- |
| 目的・ドメイン範囲・設計判断を調べる | [設計概要](docs/README.md)から対象文書だけを選ぶ |
| Domainモデル・不変条件・状態遷移・コンテキスト境界 | [Domain](.agents/rules/domain.md) |
| UseCase・Command/Query・公開契約・認可・保存前Guard | [Application](.agents/rules/application.md) |
| 永続化・DB制約・トランザクション・DI・migration | [Infrastructure](.agents/rules/infrastructure.md) |
| HTTPルート・入出力・認証窓口・例外翻訳・OpenAPI | [Presentation](.agents/rules/presentation.md) |
| テスト・静的検査・CI・フロントエンド・開発環境 | [開発ガイド](docs/development.md)の対象節 |
| コード間の関係・呼出し経路・影響範囲の調査 | [graphify](.agents/rules/graphify.md) |

`.agents/rules/`は読み込み条件と参照先だけを持ち、設計・手順の本文はdocsへ集約する。
docsは目的・境界・判断理由・外部根拠・開発上の注意点を扱い、コードや設定の網羅表を複製しない。
`docs/reports/`は確認日つきの記録として後から更新せず、当時の互換性方針を現在の要件へ引き継がない。

## コマンド & 品質ゲート

バックエンド変更では次を実行する。mypy strictとRuffを通す。個別検査とDB準備の手順は[開発ガイド](docs/development.md)を参照する。

```bash
pnpm install --frozen-lockfile
pnpm sync:backend
pnpm test:backend
pnpm typecheck:backend
pnpm lint:backend
pnpm format:check
pnpm imports
```

実DB変更では専用DBを用意し、次のBash例をルートから実行する。接続先の注意点は[開発ガイド](docs/development.md#実postgresqlの結合テスト)を参照する。

```bash
pnpm db:up
set -a; [ -f .env ] && . ./.env; set +a
TEST_DATABASE_URL=postgresql+asyncpg://pharmacydomain:pharmacydomain-dev-password@127.0.0.1:${POSTGRES_PORT:-5432}/pharmacydomain \
  pnpm test:integration
```

フロントエンド変更では次を実行する。JSのlockfileはルートの`pnpm-lock.yaml`だけを管理する。

```bash
pnpm typecheck:frontend
pnpm lint:frontend
pnpm test:frontend
pnpm build
pnpm test:e2e
pnpm test:stories
pnpm build:storybook
```

ゲートを増減するときは、本節・`.github/workflows/quality-gate.yml`・`backend/tests/tools/test_ci_quality_gate.py`の`REQUIRED_GATES`を揃える。
