# Applicationハーネス移植のレビュー修正

確認日: 2026-10-28。PR #80のP1指摘に対応したローカル検証のスナップショット。前の検証記録は初回実装時の記録として保持する。

## 指摘と変更

[操作者の有効性判定と権限構築の指摘](https://github.com/SatohaCC/PharmacyDomain/pull/80#discussion_r4401275394)を受け、ResolveActorUseCaseへ利用状態の判断とActorの構築を戻した。初回移植ではReaderがこの判断まで持っていたため、全静的規則の適合と別に責務を修正する必要があった。

Readerのget_by_subjectは、アカウント・本人・法人所属の不変な参照事実だけを返す。Applicationが確認済みの外部主体から検索し、アカウント停止、主体や本人の不一致、所属の欠落・停止・別アカウントへの対応を拒否する。有効なベンダー管理者の全法人権限、所属ロールと店舗範囲もApplicationが構築する。旧readメソッドによるActor返却経路は残していない。

永続化を伴わないReaderフェイクから、停止状態や不整合のある事実を渡すテストを追加した。Reader実装についても、停止状態を認可せず参照事実として返すことを確認した。

## 検証

| 検証 | 結果 |
| --- | --- |
| 操作者の対応範囲 | 20 passed（新規12ケースを含む） |
| pnpm test:backend | 3,600 passed、213 skipped |
| pnpm test:integration | 実PostgreSQLで213 passed、3,600 deselected |
| pnpm typecheck:backend | strict mypy、1,006ソースで成功 |
| pnpm lint:backend | Ruff成功、Domain/Applicationとも違反ゼロ |
| ハーネス自己検証 | Domain77件・Application76件成功 |
| pnpm imports | 18契約すべて成功 |
| pnpm format:check | 成功 |

結合テストの接続先はルート.envのPOSTGRES_PORTを明示読込した。実CSVサンプル不在の任意テストはskipのままで、Starlette/httpxの既存警告が1件ある。CIはこの記録の作成後に再実行する。
