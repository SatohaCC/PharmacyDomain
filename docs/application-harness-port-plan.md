# Applicationハーネス移植計画・テスト仕様

作成日: 2026-10-28。状態: 実装完了。全規則APP000〜APP015への適合まで承認済み。

実施結果は[検証記録](reports/2026-10-28-application-harness-port.md)を参照する。

## 範囲と移植元

medi-chatのscripts/checks/application_architecture.py、backend/tests/architecture/test_application_harness.py、backend/application-architecture.tomlを基に移植する。対象ソースは実行せずASTで検査する。個別違反の抑制やbaselineは追加しない。Pythonはbackend配下に置き、日本語の診断とstrict mypyへ合わせる。

Domain移植PRのコミット97fed1fを土台に専用作業ツリーで実施する。元の作業ツリーの未コミット変更は保持し、この変更へ取り込まない。

## 配置の対応

| 現行 | 移行先 |
| --- | --- |
| 各業務コンテキストの更新UseCase・専用入力・結果 | commands/操作名.py |
| 各業務コンテキストの取得・一覧UseCase・専用Query | queries/操作名.py |
| Command/Queryが混在するbusiness_hours・event_definition・category_catalog等 | 操作ごとのcommands/・queries/へ分離 |
| inputs.py・input_models.py | commands/models.pyまたは操作固有入力へ |
| 複数参照で使うDTO | queries/dtos/意味のある名前.py |
| 更新結果として共有するDTO | commands/dtos/意味のある名前.py。参照DTOに依存させない |
| reference(s).py・境界Protocol | interfaces/能力名.py |
| support.py・変換・投影処理 | commands/services/またはqueries/services/。値だけの共通処理はvaluesへ |
| exceptions.py | errors.py |
| 参照UseCaseのRepository依存 | interfaces/*_query_reader.pyとInfrastructureの明示投影 |
| commonの時計・UoW・ロック等 | 標準ライブラリだけに依存する共通契約として所有権を維持 |
| access_controlの認可・操作者 | 業務コンテキストへ依存しない認可境界として維持 |
| compositionの横断接続・保存前Guard・実行スコープ | 接続・実行スコープの責務を明示し、具象生成はInfrastructure/Bootstrapに維持 |
| integration/nsipsの入力解析・取り込み | 入力契約と更新処理を分離。技術的解析はInfrastructureへ |
| package.json・pytest・ルール文書 | 標準lintへ検査器と自己検証を接続。既存ゲートを維持 |

## 受入条件とテスト

- APP000〜APP015それぞれの禁止例・許可例を検証する。相対・別名・package形式・関数内・型専用importも検査する。
- コンテキスト宣言の網羅性、公開先の実在、循環、Command/Queryの共有禁止、QueryからDomain Repositoryの参照禁止を強制する。
- 検査器は違反なし0・違反あり1・設定不正2を返す。JSON診断・対象限定・cwd独立を確認する。通常lintは全規則を使う。
- 跨テナント404、店舗認可とSQL取得範囲、本人特定、保存前Guardとロック、時計注入を保持する。
- QueryReaderは更新操作を持たず、Application所有の不変な参照モデル・DTOを返す。Domain集約の戻り値やRepositoryの別名で置き換えない。
- フェイク・PostgreSQL双方を同じ契約へ接続し、Protocol全メンバ実装を検査する。
- pnpm test:backend / typecheck:backend / lint:backend / format:check / importsを通す。PostgreSQL結合テストはルート.envのPOSTGRES_PORTを明示読込して実行する。
- AST検査だけで業務意味や任意の実行時挙動を保証したとせず、業務テスト・保存復元・HTTP経路を併せて確認する。

## 着手順

検査器の合成テスト → 初回診断 → 配置と契約の分離 → 読取アダプタ・DI・利用側・テストの更新 → 既存Import Linter契約との整合 → 全規則違反ゼロと品質ゲートを確認する。
