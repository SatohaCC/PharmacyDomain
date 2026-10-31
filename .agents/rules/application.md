---
trigger: model_decision
description: backend/app/applicationのUseCase・Command/Query・公開契約・認可・保存前Guardを変更またはレビューするとき。
---

# Applicationの参照先

[Application設計](../../docs/design/application.md)の対象節を読み、許可依存と公開範囲は`backend/application-architecture.toml`で確認する。
認証方式を扱う場合だけ[ローカル認証](../../docs/local-authentication.md)も読む。
検査器や依存契約を変更するときは[ハーネスの運用](../../docs/development.md#静的検査とハーネス)を読む。
