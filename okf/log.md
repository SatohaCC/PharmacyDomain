---
type: Log
title: PharmacyDomain Knowledge Base 変更・決定ログ
description: PharmacyDomain プロジェクトにおけるアーキテクチャ判断、ドメインモデル変更、OKF ナレッジベースの更新履歴。
okf_version: "0.2"
timestamp: 2026-08-23T00:00:00Z
tags: [okf, adr, log, changelog, history]
status: active
---

# PharmacyDomain Knowledge Base 変更・決定ログ

本ドキュメントは、OKF（Open Knowledge Format）仕様の予約ファイル `log.md` として、プロジェクトにおける設計判断（ADR: Architecture Decision Record）、ドメインモデルの改定、ナレッジベース自体の更新履歴を時系列で記録します。

---

## 2026-08-23: 処方箋・調剤・薬歴コンテキストの仕様先行策定と規格出典の是正

- **種別**: コンテキスト設計 / ADR / ナレッジベース是正
- **概要**:
  - `okf/ddd/prescription.md`、`okf/ddd/dispensing.md`、`okf/ddd/medication_history.md` を新規作成。**設計のみで実装は存在しない**ため `status: draft` とし、各文書末尾に「実装時に更新が必要な強制点」を置いた。
  - 初稿を `okf/refa/` の規格PDFと突き合わせて是正した（下記ADR）。

### ADR-1: 別表番号は規格名まで明記する

初稿は「JAHIS レコードNo.201 / 別表15」のように、**JAHIS のレコード番号と電子処方箋（処方編）の別表番号を1つの出典文字列に混ぜて**いた。JAHIS Ver.1.11 の付録別表は 別表1:都道府県コード / 別表2:年号区分コード / 別表3:診療科コード / 別表4:レセプト種別コード の4つのみで、剤形区分・薬品コード種別はレコードの備考欄にインライン定義される。別表13:剤形区分（処方）・別表15:薬品コード種別は**処方編Ver2.4 の別表**である。両規格はレコード番号を共有するが別表番号は共有しない。**出典は規格名まで書く**ことをルールとした。

### ADR-2: 薬品コード種別は `PrescriptionSourceType` に依存して検証する

上記の取り違えは実害を生んでいた。処方編 別表15 は `1:コードなし` `3:厚生省コード` `6:HOTコード` を「（未使用）」「（使用しない）」として排除しており、電子処方箋で使えるのは `2:レセプト電算` `4:YJ` `7:一般名` のみである。JAHIS（紙）は6値すべて使用可。初稿は6値を単一 enum として列挙していたため、電子処方箋に送信不能なコードを凍結できてしまう状態だった。`MedicineIdentifier`（`code_type` と `code` を不可分に束ねるVO）を導入し、`source_type == ELECTRONIC` のとき使用可能な code_type を集約が検証する。

### ADR-3: 特殊公費は `ClaimCoveragePriority` へ写さない

処方箋の公費枠は 第一/第二/第三/**特殊**（JAHIS レコードNo.27〜30）、電子レセプトの公費枠は 第一〜**第四**（`ClaimCoveragePriority` は 1..4）であり、**両者は別軸**である。特殊公費の負担者番号・受給者番号は `N20`（漢字半角混在可・数字以外可。規格サンプル `30,特－１２,１２３４５６７`）で、「各番号が8桁・7桁以上及び数字以外の公費専用」と定義されている。これを priority 4 に写すと `ClaimPublicPayerNumber`（8桁）・`ClaimPublicRecipientNumber`（7桁）の桁数不変条件を壊すため、**特殊公費は Claim へ写さない**。

### ADR-4: 頭書き（`PatientMedicalProfile`）は薬歴からの投影とする

初稿は薬歴と頭書きを1ユースケース内で連続 `save()` し「即時リフレッシュ」と記述していたが、本リポジトリに `UnitOfWork` は存在せず原子性の裏付けがなかった。永続化実装が1つも無い段階で UnitOfWork を導入するのは先回りであるため、**頭書きを投影と定義**する。真は `MedicationHistoryRecord`（`ProfileUpdateIntents` に差分を保持）であり、頭書きは全薬歴を `counseled_at` 昇順に畳み込めば決定的に再構築できる。保存順序を `save(record)` → `save(profile)` に固定し、後者が失敗した場合は再構築で回復する。**薬歴に由来しない頭書きの直接編集は禁止**（許すと再構築が成立しなくなる）。

### ADR-5: 変更調剤は単一 enum ではなく3軸で表現する

初稿の `SubstitutionCategory` は「後発品変更」「減数調剤」「一包化」「計量混合」を1つの enum・1フィールドに載せていたため、同一薬品で同時に起こるこれらを1つしか記録できなかった。また `original_medicine_code` が一包化では常に `None` になっていた。**軸1: 何を出したか**（`DispensedMedicine.substitution` 0..1、元薬品必須）、**軸2: どれだけ出したか**（`DispensedRp.quantity_adjustment` 0..1）、**軸3: どう加工したか**（`DispensedMedicine.preparations` 0..N）に分解した。加算の排他（自家製剤×計量混合、外来服薬支援料2×両者）は算定ルールであり Dispensing の不変条件から外し、Claim の責務とした。

### ADR-6: 状態と重複する導出値を持たない

- `Prescription` から `INQUIRING` 状態を削除し、`has_open_inquiry`（未回答の照会が存在するか）からの導出とした。状態として持つと「照会解決後にどの状態へ戻すか」が `status` だけでは決まらず、かつ「`INQUIRING` なのに未回答照会が0件」という矛盾が構築可能になる。
- `ConcurrentMedicationRecord` から `is_active: bool` を削除し、`ended_on` からの導出（`is_active_on(target_date)`）とした。**この `is_active` は集約ルートのフィールドではないため `tests/domain/test_lifecycle_dialects.py` の分類対象外であり、仕組みでは止まらない**点を各文書に明記した。
- `Prescription` に終端 `DISPENSED` を追加した。遷移契機は調剤編 `リフィル処方箋情報レコード(521)` の調剤終了区分であり、「総使用回数に達したこと」ではない（規格は「達していないが次回以降の調剤が不要となった場合」も終了として扱う）。

### ADR-7: 分割調剤の3類型を区別する

初稿は注9（長期保存の困難性等）・注10（後発医薬品の試用）・注11（医師の分割指示）を「2〜3回」と一括りにしていたが、回数も算定も別物である（注9は上限の定めなし、注10は実質2分割固定、注11は3回までかつ合算点数を分割回数で除する）。`DispensingProcess` に `split_reason` を追加した。あわせて、リフィル・分割の各回が別薬局で行われうることから、**本コンテキストは自局実施分のみを保持する**という前提を明記した。

---

## 2026-08-23: OKF 実装・運用ルールの策定とディレクトリ整理

- **種別**: ナレッジベース仕様改定
- **概要**:
  - `GoogleCloudPlatform/knowledge-catalog` (OKF v0.2) 仕様に準拠し、`okf/rules.md`（OKF 実装・記述・運用ルール）を新規作成。
  - 予約ファイル `okf/log.md` を作成し、ADR および更新履歴の記録フォーマットを確立。
  - `okf/` 配下の全ドキュメントについて YAML Frontmatter の仕様（`okf_version: "0.2"`、`type`、`title`、`description` 等）の整合性を統一。
  - `okf/index.md` を更新し、OKF ルールと変更ログを索引に追加。

---

## 2026-08-23: 集約不変条件の強化と境界整合性の固定

- **種別**: ドメインモデル改定 / アーキテクチャ強化
- **概要**:
  - `Staff` 集約の所属履歴（`affiliations`）において、主所属の重複禁止および同一店舗の重複禁止不変条件を `Staff.validate()` で構築時に全域で強制。
  - 適用資格の選択構造を元資格ID列とスナップショットの平坦分離から、`CoverageSelection`（枠構造で元資格IDと固定値を不可分に束ねる設計）へ移行。
  - 公費順位の規則（上限4件・重複なし・第一公費から連続）を Shared Kernel（`app/base/domain/priority_rules.py`）に一元化。

---

## 2026-08-19: ドメイン整合性の強化とテストダブル適合性ゲート導入

- **種別**: 品質ゲート / アーキテクチャ強化
- **概要**:
  - 静的チェッカ `tools/check_fake_conformance.py` を導入し、テストダブルが実装する Protocol の全メンバを上書きしているかを強制。
  - 静的チェッカ `tools/check_lcom.py` によるクラス凝集度検証を導入。
  - `tools/check_imports.py` によるコンテキスト間依存の逆流・直接依存禁止ルールを強化。

---

## 2026-08-17: 資格（Coverage）と請求（Claim）の境界設計および受付（Reception）履歴

- **種別**: コンテキスト設計 / ADR
- **概要**:
  - `PatientCoverage` は個別資格の台帳として維持し、「最後に使った組み合わせ」を保持しない設計を採用。
  - 受付時の選択は `Reception` コンテキストの `CoverageSelectionRecord` に保存し、監査用日時と業務適用日を分離。
  - Coverage から Patient Aggregate への直接参照を禁止し、`PatientReferenceBoundary`（ID参照 Protocol）へ分離。

---

## 2026-08-15: PharmacyDomain 初期アーキテクチャ策定

- **種別**: 初期設計
- **概要**:
  - マルチテナント法人（`Corporate`）、店舗（`Store`）、スタッフ（`Staff`）、患者（`Patient`）のオニオンアーキテクチャを確立。
  - Domain Primitive（UUIDv7、不変オブジェクト）体系を `app/base/domain/primitives/` に整備。
  - Access Control 境界（`ActorContext`、`CorporateAccessBoundary`）の分離を定義。
