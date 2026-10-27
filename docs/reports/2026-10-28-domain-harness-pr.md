# DomainハーネスPRの分離検証記録

確認日: 2026-10-28。

## 対象

`main` の `f9639d4d98282e1d4b8030f5167efa690c8d3b12` を基に、`codex/domain-harness-port` へDomain移植分を分離した。店舗管理・ユーザー利用状態・認証・フロントエンドの既存未コミット変更は元作業ツリーに保持した。重複ファイルはmainの内容に対し、型付き生成に必要な変更だけを反映した。

先の [移植検証記録](2026-10-28-domain-harness-port.md) は既存変更と組み合わせた元作業ツリーの結果であり、PR用ブランチの検証結果は本記録を正とする。

## 結果

Python 3.14.9とコミット対象のuv.lockを使用した。

| 検査 | 結果 |
| --- | --- |
| `pnpm sync:backend` | 成功、lockfile変更なし |
| `pnpm test:backend` | 3,497成功、213スキップ |
| `pnpm test:integration` | 実PostgreSQLで213成功、3,497対象外 |
| `pnpm lint:backend` | Ruff成功、Domain違反0件、ハーネステスト77成功 |
| `pnpm typecheck:backend` | strict mypy成功、752ソースファイル |
| `pnpm imports` | 18契約成功、違反0件 |
| `pnpm format:check` | 768ファイル整形済み |
| `git diff --cached --check` | 成功 |

接続ポートは元作業ツリーのルート.envからPOSTGRES_PORTを明示読込した。Starlette/httpxの既存非推奨警告が1件残る。フロントエンドとクラウドCIの結果はこのローカル検証に含めない。
