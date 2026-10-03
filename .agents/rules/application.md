---
trigger: always_on
description: オニオンアーキテクチャ Application層（ユースケース、DTO、境界Protocol、Guard、認可）の開発ルール。
---

# Application層（ユースケース & 業務オーケストレーション）開発ルール

Application層はユースケースの実行、認可、トランザクション境界、コンテキスト間の境界接続を担当します。FastAPIやSQLAlchemyに直接依存せず、DIから注入されたProtocolを介して接続します。

## コンテキスト依存 & 認可境界

- **Applicationコンテキストの依存**: Store / Staff / Patient / Coverage / Reception / CareEvent は法人コンテキストや他コンテキストのApplication実装を import しない。対象法人の認可・有効状態は `access_control` の `CorporateAccessBoundary`（Protocol）にだけ依存させる。CoverageはPatientのAggregateやApplication実装を参照せず、ID参照Protocolまたは永続化制約で行う。Receptionは参照Boundaryに依存し、資格台帳や他Aggregateを保持しない。CareEventもID参照とBoundaryで扱う。実装 `CorporateAccessService` やComposition実装を import するのは Composition Root とテストのみ。
- **法人ライフサイクル**: `CorporateStatus.INACTIVE` の法人に対するStore / Staff / Patient / Coverage / Receptionの通常操作は `CorporateAccessService` で拒否し、状態変更はベンダーシステム管理者専用とする。Corporate自体には管理者ユーザーやロールを保持させない。
- **店舗ロールの二重防御**: `STORE_OPERATOR` / `STORE_VIEWER` は権限表（`AuthorizationService`）とSQLの取得条件（`RepositoryReadScope`）の両方で絞る。取得後に絞ると件数や存在の有無から情報が漏れる。読取範囲はテーブルごとに `READ_SCOPE_KINDS` で宣言し、**宣言の無いテーブルは読めない**。
- **Reception権限**: 資格台帳の編集・参照は `MANAGE_COVERAGE` / `VIEW_COVERAGE`、受付時の資格選択履歴の登録・参照は `MANAGE_RECEPTION` / `VIEW_RECEPTION` として分離する。到達可能なClaim UseCaseがない間はClaim権限を定義しない。

## 保存前ガード & 排他制御

- **本人未特定の更新を保存の時点で拒否する**: 監査の追記は本人とアカウントを要求するので、追記できない更新は成立しない。判定をトランザクション確定直前やFastAPIのyield依存以降へ置かず、保存前の境界（`ResolvedActorWriteGuard`）で止める。招待受諾は専用のUnit of Workから呼ぶ。
- **保存前の境界は並べて宣言する**: 本人特定・臨床集約の店舗状態・スタッフと任命の整合は `CompositeWriteGuard` に順番で並べ、Composition Root から `UnitOfWork.before_save` へ繋ぐ。検証は保存前の境界へ、別集約への書き込みはユースケースの明示的な手順へ分ける。
- **保存前の境界が読むものは、書く側と同じロックの内側で読む**: 境界が別集約を読み直して検証するなら、その集約を書くユースケースが取るのと同じキーで `OrganizationLock` を取ってから読む。ロックは対象の集約を保存するときだけ取り、`get()` では取らない。

## 入力処理 & 共通ヘルパー

- **業務日とページング**: 業務日は `app/application/common/clock.py` の `business_date(clock)` だけが決める。カーソル付きの一覧は `app/application/common/pagination.py` の `Page[T]` を返す。`dict[str, object]` で返さない。
- **空文字の正規化**: 任意項目の空文字・空白は Application 境界（`to_optional_text`）で `None` に正規化する。定義は `app/application/common/input_normalization.py` に1つだけ置き、各コンテキストの `support.py` は再エクスポートするだけに留める。
- **任意項目の変換はヘルパーへ寄せる**: `X.value if X is not None else None` を項目ごとに書かない。DTOの生成は `unwrap(X)`、入力からのプリミティブ生成は `build_optional(raw, Primitive)` を使い、`app/application/common/optional_conversion.py` に集約する。

## 契約 & テストダブル

- **Boundaryの例外契約**: 参照Boundary（Protocol）の `Raises:` に、他テナント・未存在をどの例外へ畳み込むかを明記する。他テナントのデータは存在を隠すため404相当の `XxxNotFoundError` に揃え、`AuthorizationError` を送出しない。定義だけで raise されない例外を残さない。
- **テストダブルの適合性**: テストダブルは実装する Protocol を明示継承し、**全メンバを上書きする**。上書きし忘れると Protocol 本体の `...` を継承して静かに `None` を返すため、`tools/check_fake_conformance.py` が pytest 内で検出する。

## 新しいユースケースの追加手順

1. `app/application/<context>/<use_case_name>.py` に `XxxCommand` DTO と `XxxUseCase` クラスを同居作成。
2. **処理フロー**: Command 文字列 → Primitive 変換 → `CorporateAccessService` → `load_*_or_raise()` → Domain Service（検証） → 集約の `change_*`（戻り値受け直し） → `repository.save()`。認可に必要なActorはCommandへ入れず、UseCaseの依存として注入する。
3. **返却値**: ID Primitive か `XxxDto.from_entity()` とし、**集約を直接返さない**。集約を返すと、外側が適用日を取る導出を直接呼べてしまい、「いつ時点の値か」が経路ごとにばらける。`tests/application/test_use_case_return_types.py` が検出する。
4. **パッケージ初期化子**: `__init__.py` は空またはモジュールドキュメント文字列だけに保ち、利用側は定義元moduleから直接importする。`tests/application/<context>/test_<use_case_name>.py` を作成。
