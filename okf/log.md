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
