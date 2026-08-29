# PharmacyDomain

薬局ドメインを、データベースやWebフレームワークから独立したドメインモデルとして再現するPythonプロジェクトです。
DDDとオニオンアーキテクチャを用い、業務上の不変条件を型、集約、Domain Service、Repository契約、テストで保護します。

現在は法人・店舗・スタッフ・患者・資格・受付・請求・処方箋・調剤・薬歴・医薬品カタログの
Domain/Applicationモデルが中心です。本番Repository、業務HTTPルート、トランザクション境界は未実装です。

- 全体像・対象範囲・未解決事項: [docs/README.md](docs/README.md)
- 重要な設計判断と理由: [docs/decisions.md](docs/decisions.md)
- 開発規約と品質ゲート: [AGENTS.md](AGENTS.md)

現在の振る舞いは `app/`、実行可能な保証は `tests/` と `tools/` を正とします。
`docs/` はコードのAPI一覧ではなく、境界、判断理由、一次資料の解釈、未解決事項だけを扱います。
