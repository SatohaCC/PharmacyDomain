# PharmacyDomain

薬局ドメインを、技術基盤から独立したモデルとして再現します。中心は電子薬歴・服薬指導と、
それに付随する処方原本・調剤事実・患者情報です。正当な状態を表現し、不正な状態を責務のある境界で拒否できることを目指します。

## 対象範囲

レセコンから受付NSIPS単位の処方・調剤事実を受け取り、業務記録を完結させます。
調剤報酬算定、窓口会計、公費上限額の累積計算、レセプト作成は外部レセコンの責務です。
分割・リフィルの複数回またぎ追跡は、1回の受付記録とは分けて扱います。

| 領域 | 所有する事実 | 設計 |
| --- | --- | --- |
| 法人・店舗・スタッフ | テナント、店舗状態、管理薬剤師、所属・資格 | [法人](design/corporate.md)・[店舗](design/store.md) |
| Identity | 本人、アカウント、法人所属と利用範囲 | [認可](design/application.md#認証認可とテナント境界)・[認証運用](local-authentication.md) |
| Patient | 患者の同一性、自由記載の頭書き、外部ID | [患者](design/patient.md) |
| Coverage / Reception | 資格台帳・適用固定値／受信原本・訂正と受付判断 | [所有境界](design/domain.md#コンテキスト境界) |
| Prescription | 処方原本、疑義照会、調剤開始可否 | [処方箋](design/prescription.md) |
| Dispensing | 自局の1回ごとの調剤・変更調剤・鑑査 | [調剤](design/dispensing.md) |
| CareEvent | 患者に対する業務機会と種別 | [イベント](design/care_event.md) |
| MedicationHistory | 薬剤師記録と臨床プロファイルの投影 | [薬歴](design/medication_history.md) |
| MedicineCatalog | 法人に属さない時点付き参照マスタ | [参照データ](design/domain.md#参照データと時間) |

## 読む資料を選ぶ

| 調べたいこと | 参照先 |
| --- | --- |
| モデル・集約・コンテキストの設計 | [Domain](design/domain.md) |
| UseCase・公開契約・認可・保存順序 | [Application](design/application.md) |
| DBへの保存・制約・DI | [永続化とDI](design/infrastructure.md) |
| HTTP入出力・認証窓口・例外翻訳 | [HTTP境界](design/presentation.md) |
| 実装・検査・実DB・フロントエンド | [開発ガイド](development.md) |
| 共通の約束と通常の品質ゲート | [AGENTS.md](../AGENTS.md) |
| 法令・外部規格の名称と版 | [一次資料](references/README.md) |
| 採否の理由・過去の計画と検証 | [設計判断](decisions.md)・[履歴](history/README.md) |

docsは境界・判断理由・根拠・未解決事項を扱います。現在の型・API・保存形式は`backend/app/`と
`backend/migrations/`、実行可能な保証はテスト・検査器・設定を確認します。実装済み一覧や検証実績はここへ複製しません。
外部資料の解釈や業務上の未解決事項は、責務を持つ設計文書に残します。
