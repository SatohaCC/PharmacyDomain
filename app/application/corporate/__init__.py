"""法人（`corporate`）コンテキストのアプリケーションサービスと DTO。

`CorporateAccessService` はここに実装がありますが、Store / Staff のユースケースは
この具象クラスではなく `app.application.access_control.CorporateAccessBoundary`
（Protocol）にだけ依存します。実装を import するのは Composition Root とテストだけです。
"""
