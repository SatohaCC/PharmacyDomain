---
trigger: model_decision
description: backend/app/infrastructure・migrations・bootstrapの永続化、DB制約、トランザクション、DIを変更またはレビューするとき。
---

# Infrastructureの参照先

[永続化とDI](../../docs/design/infrastructure.md)の対象節を読む。
実DB検証やシード投入を行う場合は[結合テスト](../../docs/development.md#実postgresqlの結合テスト)も読む。
現在の保存形式と制約は`backend/app/infrastructure/`・`backend/migrations/`と対応テストで確認する。
