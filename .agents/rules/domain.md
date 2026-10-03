---
trigger: always_on
description: DDD Domain層（エンティティ、集約、値オブジェクト、ドメインサービス、不変条件）の開発ルール。
---

# Domain層（DDD & ビジネスロジック）開発ルール

Domain層は業務上の事実、不変条件、状態遷移を所有する最内周です。FastAPI、SQLAlchemy、Application層に一切依存しません（依存の向き: 外 → 内）。

## モデリング原則 & 基本方針

- **集約の不変性**: `Entity` / `AggregateRoot` は `@dataclass(frozen=True, eq=False, kw_only=True)`。状態変更メソッド（`change_*`）は `dataclasses.replace()` で新インスタンスを返すため**必ず戻り値を受け直す**。
- **Domain Primitive**: フィールドは `value` 1つで位置引数で生成（`StoreName("サンプル名")`）。`Base*` は継承専用としフィールドの型には使わない。IDは UUIDv7（`XxxId.generate()` / `XxxId.parse()`）。
- **複数集約ルール**: 複数集約に跨る検証（例: スタッフと店舗の法人一致）は、本物の集約を受け取る無状態 **Domain Service**（`StaffStoreAssignmentService` 等）が担当する。単一集約で完結する不変条件を Domain Service 側にも重複して置かない（片方を壊しても気づけなくなる）。
- **Repositoryの最終防衛**: Repository は Domain 層の Protocol。`save()` は実効期間の競合や有効な一意キー重複を、同一集約IDを除外した上で原子的に拒否する契約とする。事前readは早期エラー用であり原子性の代替ではない。
- **ライフサイクル表現**: 集約の無効化の表し方は `none` / `active_flag` / `status_enum` / `dated_activation` の4方言に限る。日付つき無効化（`dated_activation`）が最も表現力が高いが、遡及判定を必要とする到達可能なUseCaseが現れるまでは全集約へ広げない。方言の追加・集約の追加・既存集約の方言変更は `tests/domain/test_lifecycle_dialects.py` の表を編集しない限り pytest が落ちる。
- **無効化と一意性**: 無効化後に一意キーを再利用できるかは**集約ごとに異なる業務判断**であり、全称のルールにしない。`PatientExternalIdentifier` は有効な行にだけ一意性を要求し再利用を許す。`Staff` はスタッフコードを無効化後も再利用させない。実挙動は各コンテキストの契約テストで固定する。
- **`is_active` は集約ルートだけ**: 期間（`ended_on` 等）から導出できる子レコードに真偽フラグを足すと、同じ事実の表現が2つになり必ず食い違う。`tests/domain/test_active_flag_placement.py` が `app/domain` の全 dataclass を走査し、`is_active` を持つクラスの集合を表で固定する。
- **用量に `float` を使わない**: 実在する用量刻み（0.05刻み等）で不均等服用の合計が一致せず、正当な処方を弾く。`BaseNonNegativeDecimal` / `BasePositiveDecimal` を使い、Application境界では `str` で受けて `Decimal` へ変換する。
- **所有者のいない語彙はShared Kernelへ**: `PatientId` のような「集約の同一性」は所有コンテキストから import する。一方、薬品名・用量・用法などの語彙は `app/domain/shared/` に置く。
- **判定できないことを「該当しない」に倒さない**: 医薬品マスタが無い状態で麻薬区分を「該当しない」と答えると、麻薬処方箋の必須項目チェックが素通りする。`UNKNOWN` を明示的に持ち、Domain Service がそれを拒否する（fail-closed）。
- **Domain依存規則**: `tools/check_imports.py` で集約間の直接依存を禁止する。集約間は ID Primitive、不変Snapshot、またはBoundaryで参照する。集約モジュール単位の禁止（`"app.domain.dispensing.dispensing_process"` 等）により、`validate()` から他集約を読めないようにする。

## 各コンテキストの不変条件 & 業務ルール

### 組織（Corporate / Store / Staff / Identity）

- **店舗の状態と業務**: 業務は `STORE_OPERATION_KINDS` で「新規業務 / 継続業務 / 参照」に分類し、新規業務は有効な店舗でだけ、継続業務は閉局していない店舗でだけ許す。薬歴は作成が新規業務、確定・訂正が継続業務。
- **管理薬剤師の在任は店舗状態と別の軸**: 薬機法第7条の配置義務は、`MANAGER_REQUIRED_BY_KIND` が区分ごとに「在任を要するか」を宣言し、新規業務だけを在任日に限ることで守る。在任は `StoreManagerAssignmentRepository.find_effective()` を業務日で引いて判定し、履歴を全件読んでから絞らない。拒否は `ManagerAbsenceConflictError` として区別する。スタッフ配属・管理薬剤師任命は `StoreOperation` に載せない。
- **管理薬剤師の専任は自然人で判定する**: 薬機法第7条第3項の専任義務は法人内のスタッフではなく人にかかる。`StoreManagerAssignment` は `person_id` を持ち、排他制約の鍵を**法人IDを含めずに**人単位で張る。スタッフ単位の排他制約は置かない。複合外部キー `(staff_id, person_id) → staff_person_links(id, person_id)` によりスタッフから本人が一意に決まる。
- **開局時間は週次の予定と特例日で持つ**: `BusinessHours` は全7曜日の予定と日付を指定した特例からなる。**全曜日の宣言を必須**にし、書き漏らした曜日を定休日に倒さない。祝日は特例日として登録する。時間帯は**終了時刻を含まない半開区間**。終端の `00:00` だけをその日の24時と読む。
- **開局しているかは3値で答える**: `Store.opening_state_at()` は `OPEN` / `CLOSED` / `UNKNOWN` を返す。未登録時に「開いている」に倒さない。店舗状態が有効でなければ時間表に関わらず `CLOSED`。
- **閉局の取消は状態遷移ではなく訂正**: `Store.change_status` は閉局を終端のままにし、取消は `Store.revoke_closure()` とする。戻す先は有効ではなく**休止**とする。任命は復元しない。権限は `Permission.REVOKE_STORE_CLOSURE` でベンダーシステム管理者専用。
- **スタッフ所属履歴の不変条件**: `Staff.affiliations` は、(1) `is_primary=True` の所属が店舗を問わず互いに重ならないこと、(2) 同一 `store_id` の所属が主所属・兼務を問わず互いに重ならないことを `Staff.validate()` が構築時に強制する。導出メソッドは例外を送出しない全域関数とする。
- **退職は所属履歴へ書き込む**: `Staff.deactivate(retired_on)` は退職日を必須で受け取り、退職日以降に及ぶ所属をその日で打ち切る。退職日より後に開始する配属予約が残っている場合は `AffiliationDateConflictError` で拒否する。有効化は所属を復元しない。

### 保険・受付・請求（Patient / Coverage / Reception / Claim）

- **資格の時間境界**: `CoveragePeriod` は終了日を含む `[valid_from, valid_to]`、`CoverageActivation` は無効化発効日を含まない `[activated_on, deactivated_on)`。実効期間は両者の交差で無効化発効日当日は無効。同日再無効化は冪等として許可、異なる発効日への変更は拒否。
- **適用資格の履歴**: `PatientCoverage` は個別資格の台帳として維持し、最後に使った組み合わせを保持しない。受付時の選択は Reception の `CoverageSelectionRecord` に保存する。`CoverageValidityBoundary` で適用日ごとに再構築・等価比較し、`is_still_valid=False` を自動適用しない。
- **選択は枠で持つ**: `CoverageSelection` は医療保険枠0〜1個と公費枠0〜4個からなり、各枠が `source_coverage_id` と `values`（Claim Snapshot要素）を分離不能に1対1で束ねる。導出 property とし独立した記憶域を持たせない。
- **資格の適用枠**: 医療保険は同一患者・同一期間に1件だけで順位は1に固定。公費は第一から第四までを順位で管理し、同じ順位の期間だけを競合させる。
- **レセプト番号の桁数**: 保険者番号（`InsurerNumber`）は6桁または8桁、公費負担者番号は8桁、公費受給者番号は7桁、枝番は2桁。桁数規定のない記号・番号は空でないことを要求する。Claim 側にも同じ検証を持たせる。
- **スナップショットの必須項目**: `InsuranceCoverageSnapshot.benefit_ratio` は必須。公費は `CoverageSnapshot` で第一公費から順位が連続していることを検証する。
- **公費順位の規則は1箇所**: 「上限4件・重複なし・第一公費から連続」の判定は Shared Kernel の `app/domain/shared/priority_rules.py` の `find_priority_violation()` だけが持つ。

### 臨床・調剤・医薬品（Prescription / Dispensing / MedicationHistory / MedicineCatalog）

- **非テナントのコンテキストは `medicine_catalog` だけ**: 薬価基準は国が定めるので法人ごとに内容が違わない。`Medicine` 集約も `MedicineCatalogRepository` も法人IDを取らない。
- **参照マスタは時点で引く**: `find_effective()` と `classify()` は **`as_of` を必ず取る**。処方箋の判定に渡すのは**交付日**であって処理実行日ではない。
- **調剤録の記載事項は号の表で持ち、他コンテキストの事実はスナップショットで運ぶ**: 薬剤師法第28条の調剤録代替は施行規則第16条第1項の記載事項が揃っているかで決まる。`StatutoryDispensingRecordItem` を号の列挙とし、判定関数の表と一致させる。処方箋・患者・薬剤師の事実は `StatutoryRecordSource` で運び、既定値を置かない。充足は3値で答え、記載不足の薬歴確定は止めない（報告であって強制ではない）。
- **臨床プロファイル投影に直接編集を許さない**: `PatientMedicalProfile` は薬歴からの臨床情報の投影であり、状態変更は `apply(record)` だけ。保存順序は `save(record)` → `save(profile)` で固定し同じ UnitOfWork で確定する。頭書きは `Patient` が所有する。
