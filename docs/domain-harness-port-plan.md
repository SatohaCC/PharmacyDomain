# Domainハーネス移植計画・テスト仕様

作成日: 2026-10-28。状態: 実装完了。薬歴訂正値・外部受付原本・検索条件の型付き値への移行も承認済み。

実施結果は [検証記録](reports/2026-10-28-domain-harness-port.md) を参照する。[PR用ブランチの分離検証](reports/2026-10-28-domain-harness-pr.md) も参照する。以下は着手前に承認された計画とテスト仕様である。

## 目的と範囲

medi-chatの `scripts/checks/domain_architecture.py` と `backend/tests/architecture/test_domain_harness.py` を基に、Domainの規則を機械的に強制する。Application層の構造・設計ルールの移植は次段階とする。

対象は検査器、検査器自身のテスト、Domainルール文書、既存品質ゲートへの接続、および新規則に適合させるDomain実装。生成契約を変更した場合の呼び出し側・永続化変換・テストの修正も含むが、Applicationの再配置や独立した設計変更は含めない。既存の未コミット変更を保持する。

## 現状と移植先

| 移植元・既存資産 | 移植先・扱い |
| --- | --- |
| medi-chatのDomain AST検査器 | `backend/tools/check_domain_architecture.py` に移植。対象を `backend/app/domain`、モジュール名を `app.domain` に変更 |
| medi-chatのハーネステスト | `backend/tests/tools/test_domain_harness.py` に正常例・違反例・CLI検証を移植 |
| medi-chatのDomainハーネス文書 | `.agents/rules/domain.md` に採用規則と検証範囲を反映 |
| 既存配置・役割・initializer検査 | 重複するDomain検査を共通検査器へ集約。Domain以外の検査と本プロジェクト独自の役割検査を保持 |
| Import Linter・依存検査 | 間接依存と既存契約を保持。AST検査と役割方向の定義を整合させる |
| lint・pytest・CI | 既存のbackend lintとpytestへ接続。ゲートを増減する場合はworkflow・AGENTS.md・REQUIRED_GATESを同時更新 |

Pythonの検査器・テストはbackend配下に置き、診断文・docstring・テスト名は日本語とする。診断パスはリポジトリ相対、行番号は1始まり。対象ソースはimport・実行せずASTで読む。

## 採用規則

DOM000〜DOM013を基本とし、構文、役割別配置、空initializer、外層・他コンテキスト内部への依存禁止、役割間依存、公開IDの定義、技術依存・I/O禁止、frozen dataclass、可変コレクション禁止、生の値を保持しない業務モデル、createラッパー禁止、構築時の暗黙変換禁止、Primitive/Protocol継承、循環禁止を検査する。

次の点は移植時に本プロジェクトの契約へ合わせる。

- 公開IDは「1コンテキスト1個」を採用しない。複数集約・子EntityのIDを許可し、各IDの基底と公開先を検証する。共有操作者IDの現行所有権も保持する。
- foundationのEntity・ValueObject・Primitive基底と、その継承関係を解決する。基底の正規化と業務モデルの暗黙変換を区別する。
- Enumなどの業務上の列挙型をPrimitiveと誤判定しない。標準ライブラリの許可範囲は利用実態と純粋な値操作の責務から決め、I/Oのために拡張しない。
- 単一値の正規化はPrimitiveへ、複合不変条件はVO/Entityへ置く。業務上の生成操作は名前だけで消さず、引数変換ラッパーと業務判断を区別して移行する。
- `create()`、coverageの並べ替え、連絡先・日時の構築時変換などは、診断結果と振る舞いを確認して明示生成へ移す。違反baselineやファイル単位の抑制で通さない。
- ライフサイクル、activeフラグ、期間競合、テナント境界などの既存業務検証は保持する。

## テスト仕様・受入条件

1. 各DOM規則に独立した正常例と禁止例を用意し、期待した規則IDを検出する。実ソースが違反ゼロであることだけで検査器の正しさを判断しない。
2. 新設コンテキストを名前の登録なしで検査する。複数の正当な公開IDを許可し、ID以外の公開・不正基底・他コンテキストの内部参照を拒否する。
3. 相対import、関数内import、TYPE_CHECKING、別名・修飾名・継承、文字列注釈、ネスト型、type文とTypeAlias注釈を通した迂回を検証する。
4. 通信・ファイルI/O・プロセス実行・動的実行、可変初期値、createラッパー、構築時の暗黙変換、循環を検出する。正当な基底正規化・Enum・型付き直接生成・複合不変条件を許可する。
5. CLIは違反なし0、違反あり1、入力不正2を返す。cwdに依存せず、JSON診断と対象絞り込みを検証する。全体ゲートでは絞り込まない。
6. Domain修正は該当する業務テストで不変条件・状態遷移・正規化結果を確認し、呼び出し側と保存変換も回帰確認する。既存の不適切な生成契約を保持するためだけのテストは更新する。
7. ルートから `pnpm test:backend`、`pnpm typecheck:backend`、`pnpm lint:backend`、`pnpm format:check`、`pnpm imports` を実行する。mypy strictとRuffを通す。未コミットの既存変更に起因する失敗は切り分けて報告する。
8. 保存変換やDB経路に変更が及ぶ場合は、ルート.envのPOSTGRES_PORTを明示読込して実PostgreSQL結合テストを実行する。DBなしのskipを検証成功と扱わない。

## 着手順

承認後、既存状態の検査結果を記録し、合成コードによる検査器テスト、検査器移植、実ソースの診断、Domainと必要な利用側の修正、既存検査の集約、品質ゲート接続、最終回帰の順で進める。初回診断で想定を超える業務設計変更が必要なら、変更範囲を提示して追加承認を得る。

## 検証の限界

この計画作成時にはソース・ルール・既存検査を読んだだけで、移植後の実ソース診断や品質ゲートは未実行。全違反件数は未確定。AST検査は集約境界の妥当性や任意の実行時迂回を証明せず、業務テストとレビューを併用する。
