# 計画・判断・検証の履歴

以下は当時の検討・合意・検証を追う記録です。現行の規約・仕様は[設計概要](../README.md)とコード・検査設定を確認します。
日付付きの検証レポートは変更せず、未実施・制約・当時の結果もそのまま残します。

## 設計判断

[索引](../decisions.md)から必要な判断を選び、[本文](decisions.md)で理由・撤回・置換の経緯を確認します。

## 完了・置換済みの計画

| 計画 | 当時の状態 | 検証記録 |
| --- | --- | --- |
| [Domain命名統一](plans/domain-module-naming-plan.md) | 2026-10-18完了 | 計画内に記録 |
| [Domainハーネス移植](plans/domain-harness-port-plan.md) | 2026-10-28完了 | [移植](../reports/2026-10-28-domain-harness-port.md)・[PR分離](../reports/2026-10-28-domain-harness-pr.md) |
| [Applicationハーネス移植](plans/application-harness-port-plan.md) | 2026-10-28完了 | [移植](../reports/2026-10-28-application-harness-port.md)・[修正](../reports/2026-10-28-application-harness-review-fix.md) |
| [範囲付きユーザー権限](plans/scoped-user-permissions-plan.md) | 実装・検証完了 | [実施](../reports/2026-10-29-scoped-user-permissions.md)・[修正](../reports/2026-10-29-scoped-user-permissions-review-fix.md) |
| [旧アカウント停止案](plans/account-suspension-permissions-plan.md) | 範囲付き権限案へ置換済み | 旧案のまま保持 |

## 初期の確認記録

- [2026-09-17 実装状況](../reports/implementation-status-2026-09-17.md)
- [2026-09-23 実装レビュー](../reports/implementation-review-2026-09-23.md)
