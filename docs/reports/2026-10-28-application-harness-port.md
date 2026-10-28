# Applicationハーネス移植の検証記録

確認日: 2026-10-28。ローカル検証完了、PRのCI実行前のスナップショット。

## 対象と移植元

medi-chatの4079c9222ebcd615e84011f2fe215cd632e07ccaにあるApplication検査器・合成テスト・宣言設定を基に移植した。移植元の対象3ファイルに未コミット差分は無かった。PharmacyDomainのDomain移植PR #79を土台に専用作業ツリーで作業し、同PRを含むmainのaa1d300を取り込んだ。元の作業ツリーの未コミット変更は保持した。

APP000〜APP015を通常lintへ接続し、検査器自身の正常例・禁止例も同じlintで実行する。既存のImport Linter18契約とアーキテクチャ検査を維持し、モデル・ProtocolからHandlerへの逆依存契約を新配置へ更新した。CIのトップレベルコマンドは増減せず、既存のbackend lintの中で新しい検査を強制する。

## 実装した境界

- CommandとQueryの配置、入力、DTO、共有処理を分離した。専用Command59個はHandlerと同居し、Readerや複数操作で共有する入力だけをmodelsへ置いた。
- 31個の参照操作に読取専用QueryReaderを設け、Infrastructureの明示的な投影へ接続した。初期実装は既存のJSONB Repositoryを使って投影する。認可・公開範囲・業務日の決定とDomainサービスの業務判定はApplicationが所有する。
- 法人取得は既存の認可・存在確認の抽象境界を使い、公開DTOへ変換する。初期区分を保存する操作はEnsureCategoryCatalogUseCaseとして更新側へ配置した。
- NSIPS取込と法人契約登録は、他の具象Handlerのimportをやめ、利用側所有の能力Protocolへ接続した。横断変換・保存前Guard、実行スコープと登録情報はcompositionの責務として明示した。
- 公開境界の不変モデルと抽象認証契約を区別し、具象Serviceを公開モデルの名前で隠せないようにした。中立Protocolを経由した反対側モデルの共有も検出する。
- Command結果とQuery結果はHTTP境界で明示変換する。イベント種別一覧のtuple応答で実DBテストが検出した変換漏れに、DB不要の回帰テストを追加して修正した。
- 医薬品CSVのファイル操作と文字コード判定をInfrastructureへ移した。ApplicationとHTTP入力はcsv_textを受け取る。サーバーファイルパスを指定するfile_path入力は削除し、CLIと生成OpenAPI型も合わせた。UTF-8 BOMとCP932の読取を検証した。
- 元のApplicationモジュールのトップレベル処理を照合し、権限分類・公費対応表の起動時検査を維持した。最適化実行でも検査を失わないことを確認する回帰テストを加えた。

共通時計・UoW・ロック、信頼済み操作者、横断Guard・境界接続と実行スコープは本プロジェクトの所有権に合わせた役割として扱い、個別違反の抑制やbaselineは追加していない。

## 検証結果

| 検証 | 結果 |
| --- | --- |
| pnpm test:backend | 3,588 passed、213 skipped |
| pnpm test:integration | 213 passed、3,586 deselected |
| pnpm typecheck:backend | strict mypy、1,004ソースで成功 |
| pnpm lint:backend | Ruff成功、Domain/Applicationとも違反ゼロ |
| Domainハーネス自己検証 | 77 passed |
| Applicationハーネス自己検証 | 76 passed |
| pnpm imports | 18契約すべて成功 |
| pnpm format:check | 成功 |
| pnpm typecheck:frontend | 成功 |
| pnpm generate:api | 成功。HTTPリクエストのfile_path削除を反映 |
| 起動・認可・境界の対応範囲 | 242 passed |

結合テストはルート.envのPOSTGRES_PORTを明示読込して実PostgreSQLへ接続した。結合テストの再実行後に、起動時ガードの保持と空モジュールの除去を行い、全体回帰・型・lint・import・起動境界を再検証した。

DBなし実行のskipを実DB成功の根拠には使っていない。実CSV原本を参照する任意テスト1件はサンプルファイル不在でskipしており、実原本全件の取込はこの確認に含まない。Starlette/httpxの既存の非推奨警告が1件ある。AST検査は業務上の意味や任意の実行時迂回を完全には証明しない。
