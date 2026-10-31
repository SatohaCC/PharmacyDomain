---
trigger: model_decision
description: backend/app/presentationalのHTTPルート・認証窓口・入出力・例外翻訳・OpenAPIを変更またはレビューするとき。
---

# Presentationの参照先

[HTTP境界](../../docs/design/presentation.md)の対象節を読む。
入出力と公開UseCaseへの接続は`backend/app/presentational/`と対応する`backend/tests/presentational/`で確認する。
認可やトランザクション境界も変更する場合だけ[Application設計](../../docs/design/application.md)を読む。
