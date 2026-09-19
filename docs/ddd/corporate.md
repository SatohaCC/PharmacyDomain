---
type: Specification
title: Corporateコンテキスト概要
description: マルチテナント法人の同一性、ライフサイクル、および他コンテキストに対するテナント認可境界。
timestamp: 2026-09-19T00:00:00Z
status: active
tags: [domain, corporate, multi-tenant, access-control]
---

# Corporateコンテキスト概要

Corporateは、薬局グループ（医療法人、調剤薬局チェーン、個人経営薬局等）の法人単位の同一性と、
マルチテナントSaaSとしてのデータ隔離境界を管理します。

## 境界と階層構造

### 組織階層: 法人 ──(1:N)──> 店舗 の2層構造
システムにおける最上位のテナント境界は「法人（`Corporate`）」です。
「企業グループ（親会社・ホールディングス）」という上位エンティティは持ちません。
すべての法人は対等に完全隔離された独立テナントとして扱われます。

### ユーザーとの関係: 入れ子ツリーではなくリレーション構造
「企業グループ → 企業 → 店舗 → ユーザー」という入れ子の4階層ツリー構造は採用していません。
- **独立したユーザー**: ユーザー（本人 `AccountPerson` / アカウント `UserAccount`）は、特定の法人や店舗の配下に属する下位リソースではなく、法人の外側に独立して存在します。
- **法人アクセス権による紐付け**: ユーザーは `CorporateMembership`（メンバーシップ）を通じて、1つまたは複数の法人、およびその配下の店舗範囲に対してアクセス権（ロール）を持ちます。
- **グループ企業や兼務の表現**: 親会社エンティティを作らなくても、1人のユーザーが複数の `CorporateMembership` を保持することで、グループ内異動・転籍や系列別法人の兼務を自然かつ安全に表現できます（テナント隔離性を崩さずに運用可能）。

### 所有するもの / 所有しないもの

Corporateが所有するもの:

- 法人の同一性（`CorporateId`）
- 法人名称（`CorporateName`）および代表者名（`CorporateRepresentativeName`）
- 法人の利用状態（`CorporateStatus`: `ACTIVE` / `INACTIVE`）
- 全法人の一覧検索・カーソルページネーション（ベンダーシステム管理者向け）

所有しないもの:

- 企業グループ（親会社・ホールディングス等の上位階層は持たない）
- 店舗（Store）、スタッフ（Staff）、患者（Patient）などの詳細。すべてID参照とする
- システム利用者や認証アカウント、ロール（Identityコンテキストが所有）
- 法人の契約プランや課金情報（現時点では境界外）

他コンテキストの認可・存在確認・有効性検証は `CorporateAccessService`（`CorporateAccessBoundary`）が担当します。

## 現在出来ていること

### 1. ドメインモデルと不変条件
- **ファクトリとID採番**: UUIDv7を用いた一意な `CorporateId` を持つ法人の開設。
- **イミュータブルな状態更新**: 法人名・代表者名の変更（値オブジェクトによる空文字・不正値の正規化および検証）。
- **ライフサイクル状態（`status_enum`）**:
  - `ACTIVE`: 通常稼働状態。配下の店舗・スタッフ・調剤等の全通常業務操作を許可。
  - `INACTIVE`: 利用停止状態。他コンテキストからの通常業務操作を遮断。

### 2. ユースケース（Application層）
- **法人新規登録（`RegisterCorporateUseCase`）**: ベンダーシステム管理者による新規開設。
- **法人詳細取得（`GetCorporateUseCase`）**: 自法人管理者またはベンダーシステム管理者による詳細参照。
- **法人一覧検索（`ListCorporatesUseCase`）**: 法人名・状態による絞り込みとカーソルページネーション。
- **属性変更**: 法人名変更（`ChangeCorporateNameUseCase`）、代表者名変更（`ChangeRepresentativeUseCase`）。
- **状態変更（`ChangeCorporateStatusUseCase`）**: ベンダーシステム管理者による有効化・停止。

### 3. テナント認可境界（`CorporateAccessService`）
- 他コンテキスト（Store, Staff, Patient, Coverage, Reception 等）が操作を実行する際、必ず本境界を通じて対象法人の存在と有効性を検証。
- **404による存在秘匿**: 他テナントの法人が指定された場合、403（権限なし）ではなく404（存在しない）として扱い、他法人の存在や件数の漏洩を完全に隠蔽。
- **休止法人の遮断**: 法人が `INACTIVE` の場合、配下のリソースに対する更新・新規登録などの通常業務操作を遮断。

### 4. HTTP API（Presentational層）
- FastAPI ルータ（`/corporates`）として全ユースケースをエンドポイント公開。
- `ActorContext` による認証・ロール認可と、エラー応答の標準化。
- 存在秘匿（他法人のID指定時は 404 応答）。

### 5. 永続化と同時実行制御（Infrastructure層）
- PostgreSQL Repository（`CorporateRepository`, `CorporateSearchRepository`）による完全な永続化。
- 楽観ロック（バージョン制御）による同時更新の衝突防止。
- 実PostgreSQL結合テストおよびインメモリFake実装によるテスト保証。

## 重要な設計判断

- **Corporate集約に管理者やロールを持たせない**: 法人にユーザーを直持ちさせず、Identityコンテキスト（`AccountPerson`, `UserAccount`, `CorporateMembership`）に分離することで、M&Aや転職、複数法人兼務に耐えうる設計とする。
- **存在秘匿（404エラー）の徹底**: マルチテナント環境において、悪意のある操作者が総当たりで法人IDを探索しても、法人の存在有無が漏れないようにする。
- **他コンテキストのApplication非依存**: Store, Staff, Patient など他コンテキストは Corporate のApplication実装を直接 import せず、`CorporateAccessBoundary` Protocol にのみ依存する。

## 未解決事項

- 法人ごとの業務設定・安全管理ポリシー（例: 調剤鑑査の二重チェック強制フラグ等）は未実装。必要時はApplication層の設定注入として扱う方針。
- 契約プラン、課金・請求情報の管理は未実装。
