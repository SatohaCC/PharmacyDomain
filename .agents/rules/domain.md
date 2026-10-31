---
trigger: model_decision
description: backend/app/domainのモデル・状態遷移・コンテキスト境界を変更またはレビューするとき。
---

# Domainの参照先

[Domain設計](../../docs/design/domain.md)を読み、業務の背景が必要な場合だけリンク先の対象コンテキストを読む。
現在の型と不変条件は`backend/app/domain/`と対応する`backend/tests/domain/`・`backend/tests/contracts/`で確認する。
配置・型構造の検査を変更するときは[ハーネスの運用](../../docs/development.md#静的検査とハーネス)を読む。
