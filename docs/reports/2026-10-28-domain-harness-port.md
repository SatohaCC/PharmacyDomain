# Domainハーネス移植の検証記録

確認日: 2026-10-28。

## 実装範囲

medi-chatのDomain AST検査器と違反例テストを移植した。実装は `backend/tools/check_domain_architecture.py`、検査器自身のテストは `backend/tests/tools/test_domain_harness.py` に置いた。

DOM000〜DOM013により、配置、空initializer、依存方向、公開ID、技術依存禁止、不変性、型付きフィールド、直接生成、構築時の暗黙変換禁止、役割と継承、循環を検査する。新設コンテキストは自動検出する。公開IDは本プロジェクトの複数集約に合わせて複数定義を許可し、既存のShared KernelとEnum・共通基底の責務を保持した。

配置・役割テストの判定実装は検査器へ集約した。既存のImport Linterと業務上の不変条件テストは維持した。既存のbackend lintへ検査器と検査器自身のテストを接続したため、CIが既に実行する品質ゲートを通じて強制される。ルートのゲート集合は増減していない。

Domainの生成ラッパーを削除し、呼び出し側を型付き直接生成へ揃えた。生の値を保持していた検索条件・算定加算・訂正記録・受付原本などはPrimitiveと閉じた型の集合で表現する。IDを持つ薬歴訂正と配列要素は子Entityとして配置した。宣言型ガードと保存codecは型別名を解決する。

頭書き日時の検証・UTC正規化は日時Primitiveが所有する。公費枠は利用側で明示的に順位順へ整え、Domainは逆順入力を暗黙に並べ替えず拒否する。VO/Entityのフィールド置換フックは削除した。

Application層の構造ハーネスは移植していない。Application・Infrastructureの変更はDomainの生成・保存・出力契約に必要な変換である。着手前から存在した未コミット変更を保持した。コミット・pushは行っていない。

## 検証結果

| 検査 | 結果 |
| --- | --- |
| 着手前の `pnpm test:backend` | 3,392成功、222スキップ |
| 移植後の `pnpm test:backend` | 3,503成功、222スキップ |
| 実PostgreSQLの `pnpm test:integration` | 222成功、3,503対象外 |
| `pnpm lint:backend` | Ruff成功、Domain違反0件、ハーネステスト77成功 |
| `pnpm typecheck:backend` | strict mypy成功、760ソースファイル |
| `pnpm imports` | 18契約成功、違反0件 |
| `pnpm format:check` | 777ファイル整形済み |
| 最後の処方生成整理に対する対象回帰 | 151成功 |
| `git diff --check` | 成功 |

実DBの接続先はルート `.env` の `POSTGRES_PORT` を明示的に読み込んで組み立てた。DBなしのスキップを実DB検証の成功とは扱っていない。既存のStarlette/httpx非推奨警告が1件残る。フロントエンドの機能検証とクラウドCIは今回実行していない。

このハーネスは対象ソースを実行しない静的検査であり、任意の実行時迂回や業務設計の妥当性を証明するものではない。業務の振る舞いは個別テストと実DBの回帰で併せて検証した。
