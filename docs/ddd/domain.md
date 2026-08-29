---
type: Guideline
title: Domain層の設計概要
description: PharmacyDomain のコンテキスト境界、ドメインモデルの原則、重要な不変条件の置き場所。
timestamp: 2026-08-29T00:00:00Z
status: active
tags: [backend, domain, ddd, architecture]
---

# Domain層の設計概要

Domain層は業務上の事実、不変条件、状態遷移を所有する最内周です。
FastAPI、DB、Application層へ依存しません。現在の型やメソッドの詳細は `app/domain/`、
保証されている条件は `tests/domain/` を直接確認します。

## コンテキスト境界

| 領域 | コンテキスト | 境界の要点 |
| :--- | :--- | :--- |
| 組織 | Corporate / Store / Staff | 法人をテナント境界とし、店舗所属は履歴として扱う |
| 患者・保険 | Patient / Coverage / Reception / Claim | 資格台帳、受付時選択、請求Snapshotを別の事実として分ける |
| 調剤業務 | Prescription / Dispensing / MedicationHistory | 原本、調剤作業、服薬指導記録を別集約で管理する |
| 参照データ | MedicineCatalog | 国が定める非テナントの版付きマスタとして扱う |

各コンテキストは他集約のEntityを保持せず、所有元のID Primitiveで参照します。
複数集約を同時に見なければ判定できない規則だけを、無状態のDomain Serviceへ置きます。
存在確認、認可、外部コンテキストからの参照はApplication Boundaryの責務です。

## モデルの原則

### Domain PrimitiveとValue Object

- Domain Primitiveは `value` 1つを持ち、生成時に正規化と検証を完了する
- `Base*` は継承専用とし、フィールドには意味のある具象型を使う
- 集約IDはUUIDv7とし、所有コンテキストが型を定義する
- 所有者のいない薬品名、用量、用法などの語彙だけをShared Kernelへ置く
- 用量は丸め誤差を避けるため `Decimal` で表現し、`float` を受け付けない

### EntityとAggregate Root

- `frozen=True, eq=False, kw_only=True` の不変オブジェクトとする
- 状態変更は `dataclasses.replace()` を使って新しいインスタンスを返す
- 同一性の比較と、状態内容の比較を混同しない
- 構築できない状態は、読み取り時ではなく構築・変更時に拒否する

### Repository

RepositoryはDomain層のProtocolです。Applicationの事前readは分かりやすいエラーのために使いますが、
一意性や期間競合の最終防衛は `save()` の原子的な契約です。
本番永続化がない現状では、この原子性は未証明です。

## 時間とライフサイクル

「有効」の意味は集約ごとに異なるため、次の4方言だけを使います。

| 方言 | 意味 |
| :--- | :--- |
| `none` | 無効化を持たない |
| `active_flag` | 現在の有効・無効だけを持つ |
| `status_enum` | 業務状態遷移を持つ |
| `dated_activation` | 適用日を指定して有効性を判定する |

方言の選択と一意キー再利用可否は同じ判断ではありません。
集約を追加・変更するときは `tests/domain/test_lifecycle_dialects.py` の表も変更し、
意図しない第5の表現を作りません。

時間区間は明示します。特にCoverageでは制度期間を終了日込み、
有効化区間を無効化発効日を含まない区間として扱います。
参照マスタは処理時点の「今」ではなく、処方箋交付日などの業務上の対象時点で引きます。

## 重要な設計判断

- 資格台帳は履歴の真実、Receptionの選択はその時点の業務判断、Claim Snapshotは請求用の固定値である
- CoverageSelectionは元資格IDと固定値を同じ枠に束ね、並び順の暗黙契約を作らない
- 公費順位の規則本体はShared Kernelの1箇所に置き、CoverageとClaimは各自の例外へ変換する
- 医薬品規制区分が不明な場合は非該当に倒さず、危険な処方をfail-closedで拒否する
- 子レコードに、期間から導出できる `is_active` を重ねて持たせない
- 患者医療プロファイルは薬歴からの投影とし、直接編集できる独立集約にはしない
- 無効化後の一意キー再利用は全称ルールにせず、患者外部IDとスタッフコードで別に判断する

Prescription、Dispensing、MedicationHistoryの背景は各文書を参照してください。

- [Prescription](prescription.md)
- [Dispensing](dispensing.md)
- [MedicationHistory](medication_history.md)

## 機械的な強制

依存方向は `tools/check_imports.py`、ライフサイクル表現やactive flagの配置はDomainテスト、
Repository契約は `tests/contracts/`、FakeのProtocol適合は `tools/check_fake_conformance.py` が検査します。
設定と実行コマンドは [AGENTS.md](../../AGENTS.md) が正典です。

## 未解決事項

- 本番RepositoryとDB制約がなく、競合時の原子性を証明できない
- Unit of Workがなく、複数集約保存の途中失敗を一括でロールバックできない
- Infrastructureがないため、保持期間、監査、移行、マスタ取り込みの運用設計が残る
