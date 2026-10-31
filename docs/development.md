# 開発ガイド

実装・検証で必要な節だけを参照します。通常の品質ゲートは[AGENTS.md](../AGENTS.md)、
実際の実行内容はルートとbackend・frontendのpackage.jsonおよびCI設定を正とします。
この文書の`app/`・`tests/`・`tools/`・`migrations/`・`pyproject.toml`はbackendからの相対パスです。

## Pythonパッケージとテスト

`app/`・`tests/`・`tools/`・`migrations/`でPythonモジュールを持つディレクトリは`__init__.py`を置きます。
名前空間パッケージのままでは、ディレクトリ単独のpytest実行や同名モジュールの収集でimportが壊れます。
初期化子は空かモジュールドキュメント文字列だけとし、利用側は定義元から明示importします。
UseCase追加時に`__all__`や再エクスポートを増やしません。

テストは実オブジェクトとインメモリRepositoryを使い、Protocolを継承するFake・Adapterは全メンバを実装します。
業務判定・保存結果・認可拒否のタイミングを観測し、実DB固有の保証は結合テストで確認します。

## 静的検査とハーネス

標準リンターが同じ保証を提供できる規則は標準設定へ集約し、Domain固有の不変性・型構造や
Application固有の公開面・Command/Query分離は独自検査で補います。
移行時は直接・別名・型専用・関数内import、許可例、抑制コメントを含めて違反注入を比較し、
既存の保証を弱めてから独自検査を削除する順序にはしません。

依存規則の正典は`pyproject.toml`のImport Linter・import_rules設定と`application-architecture.toml`です。
新コンテキスト・役割モジュール・UseCaseを追加したときは、依存方向・公開先・禁止先の網羅性と違反注入を確認します。
foundation・shared・Application commonの許可範囲も更新し、未登録の名前で検査をすり抜けさせません。

Ruffは相対import・ワイルドカード・禁止APIを検査します。公開JSON・保存JSONはasdictへ委譲せず明示変換します。
抑制コメントには対象コードを明記し、必要な技術処理の行だけを例外にします。
Domain/Applicationの境界規則は通常lintから`lint:boundaries`を呼び、`--ignore-noqa`で検査します。
Ruffが検出しない直接の`__import__()`はDomain/ApplicationのAST検査で補います。

独自検査は循環・依存の許可リスト・凝集度・Protocol適合・Domain型構造・Application配置と公開契約を担当します。
通常ゲートは検査器と正常例・禁止例の自己検証を実行します。対象やphaseを絞った診断の成功を全規則適合とは報告しません。
検査規則を追加する場合は文章だけでなく設定・検査器と違反注入にも反映します。

個別診断はリポジトリルートから実行します。

```bash
pnpm --filter pharmacydomain-api exec uv run python -m tools.check_imports --verbose --fail-on-violation
pnpm --filter pharmacydomain-api exec uv run python -m tools.check_lcom --verbose --fail-on-violation
pnpm --filter pharmacydomain-api exec uv run python -m tools.check_fake_conformance --verbose --fail-on-violation
pnpm --filter pharmacydomain-api lint:boundaries
pnpm --filter pharmacydomain-api lint:domain
pnpm --filter pharmacydomain-api lint:domain:harness
pnpm --filter pharmacydomain-api lint:application
pnpm --filter pharmacydomain-api lint:application:harness
```

Domain/ApplicationのAST検査器は対象コードを実行せず、リポジトリ相対パス・1始まりの行番号・規則IDを返します。
終了コードは適合0・違反1・設定または入力不正2です。JSON診断と対象限定は診断用途に使います。
ASTで業務意味や任意の実行時動作を完全には保証できないため、業務・HTTP・実DBテストを併用します。

## 実PostgreSQLの結合テスト

実DBを要するテストは`tests/integration/`へ置きます。マーカーはそのconftestが自動で付け、
`TEST_DATABASE_URL`未設定時はスキップします。CIはPostgreSQLを持つ専用ジョブで実行します。
スキップは未検証です。DBなしのテスト成功から制約・競合・ドライバ挙動を確認済みとは報告しません。

結合テストはスキーマ再作成とテスト間のTRUNCATEを行うため、専用テストDBへ接続します。
composeの公開ポートはルート`.env`の`POSTGRES_PORT`を使います。シェルは`.env`を自動読込しないので、
接続URLを組み立てる前に明示読込します。[AGENTS.mdの実行例](../AGENTS.md#コマンド--品質ゲート)を使います。

過去スキーマへのデータ投入とシード保存順は[永続化とDI](design/infrastructure.md)を参照します。

## フロントエンド

React・TypeScript・TanStack RouterのSPAとし、API型はOpenAPIから生成します。
業務判断と最終認可はバックエンドが所有し、招待秘密をログ・永続ストレージへ保存しません。

routesはURL・認証ガード・画面接続、featuresのviewは表示、画面用hookは状態と非同期処理、
modelはReact非依存の規則、apiは通信を担当します。React Aria ComponentsとStyleXはshared/ui内部と
ビルド設定に限定し、画面のpropsへライブラリ固有の型を漏らしません。境界はESLintと違反注入で検証します。

部品・主要viewにStorybookを併置し、実API・認証なしで状態を確認できるようにします。
表示用データの名称は「テスト薬局」「テスト 太郎」など「テスト」を含めます。
操作とアクセシビリティはVitest addonの実ブラウザテストで検証し、画像比較とは区別します。
`pnpm storybook`で表示を確認し、静的ビルド後の`pnpm test:visual`で画像比較を行います。
基準画像は内容を確認してから更新します。

## 文書の更新

設計・業務の本文はdocs、読み込み条件と参照先は`.agents/rules/`、共通の約束と通常ゲートはAGENTS.mdへ置きます。
同じ規則を複数の本文へ複製せず、対象節へのリンクで接続します。型・フィールド・テスト・不変条件の網羅表はコードや設定に任せます。
目的・境界・採否の理由・一次資料の解釈・未解決事項が変わるときに通常文書を更新します。
日付付きの完了計画と`docs/reports/`は当時の記録として扱い、現在の規約は各設計文書とコードで確認します。
