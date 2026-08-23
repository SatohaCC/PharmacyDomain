---
type: Guideline
title: Domain層の実装ガイドライン
description: ドメイン層の設計思想、基底クラスの役割、および実装手順。
tags: [backend, domain, primitives, value-object, ddd]
timestamp: 2026-08-15T00:00:00Z
---

# Domain層の実装ガイドライン

PharmacyDomain プロジェクトにおけるドメイン層（Domain Layer）の設計思想、構成要素、基底クラスの活用方法、および実装パターンについてのガイドラインです。

---

## 1. 構成要素と基本原則

ドメイン層は、ビジネスルールやドメイン知識を表現する最重要な層です。フレームワークやデータベースなどの外部依存を持ちません。

| 構成要素 | 概要 | 主な特徴・識別方法 |
| :--- | :--- | :--- |
| **Domain Primitive** | 単一の値をカプセル化する最小単位の値オブジェクト | `DomainPrimitive[T]` を継承。`@dataclass(frozen=True)`（`kw_only`なし）。不変、自動正規化・バリデーション。`Base*` は直接使わず派生させる。 |
| **Value Object** | ドメインの概念を表す値の組み合わせ | `@dataclass(frozen=True, kw_only=True)`。不変、属性値による等価性比較。 |
| **Domain Entity** | ライフサイクルと識別子（ID）を持つオブジェクト | `Entity[ID]` を継承。`@dataclass(frozen=True, eq=False, kw_only=True)`。IDによる同一性比較。状態変更は新しいインスタンスを返す。 |
| **Aggregate Root** | 整合性境界を守るルートエンティティ | `AggregateRoot[ID]` を継承。リポジトリで直接永続化される単位。 |
| **Domain Service** | 単一のオブジェクトに属さないドメイン知識・業務ロジック | 無状態（Stateless）。リポジトリ等を利用した重複チェック、複数集約の整合性検証など。 |
| **Domain Repository** | 集約を取得・保存するための抽象インターフェース | `Protocol`で定義し、Domain層はデータベースやORMの詳細を知らない。 |

---

## 2. Domain Primitive

単一の値（文字列、数値、日付など）に対する不確実性を取り除き、自己検証を行うオブジェクトです。

### 特徴
- **不変（Immutable）**: `@dataclass(frozen=True)` を付与し、生成後に内部の値を変更できません。
- **自動バリデーション**: インスタンス生成時に正規化（`_normalize`）とルール検証（`validate`）を実行します。
- **不正状態の排除**: 不正な値（空文字、フォーマット違反など）を持つインスタンスの存在を許しません。
- **位置引数で生成する**: `StoreName("サンプル薬局")` のように書きます。

### 正規化と検証の順序

`DomainPrimitive.__post_init__` は次の順で動きます。

1. `_normalize(self.value)` を呼ぶ。
2. 正規化結果が元の値と異なる場合（型が変わった場合を含む）だけ、`object.__setattr__` で `value` を1度だけ書き戻す。
3. `validate()` を実行する。

`frozen=True` の値を書き換えているのはこの1箇所だけです。生成後に外から書き換える経路は用意しません。
`_normalize` は派生クラスで任意にオーバーライドできるフック（既定は素通し）、`validate` は `@abstractmethod` なので必ず実装します。

### `Base*` は直接インスタンス化しない

`Base*` の接頭辞が付いたプリミティブは**継承用**です。フィールドの型として直接使わず、
コンテキストごとに派生クラスを定義します（`BaseTelephoneNumber` → `StorePhoneNumber` /
`StoreFaxNumber`）。

理由は2つあります。1つは型の分離で、`ContactInfo` の電話番号とFAX番号のように
同じ基底から派生した項目を取り違えられなくするためです。もう1つはエラーメッセージで、
基底クラスを直接使うと項目名が空のまま「は0で始まる…」のように提示されてしまいます。

> **現状の例外**: `Staff.phone_number` / `Staff.email` は `BaseTelephoneNumber` / `BaseEmailAddress` を、
> `InsurancePharmacistRegistration.registration_number` は `BaseNormalizedString` をそのままフィールド型に
> しています。スタッフコンテキストに専用の派生クラスを用意する余地が残っています。

### エラーメッセージの項目名

**全プリミティブ共通の項目名の仕組みはありません。** 用意されているのは次の2つだけです。

| 仕組み | 定義場所 | 用途 |
| :--- | :--- | :--- |
| `identifier_name` | `EntityUUID`（`ClassVar[str] = "識別子"`） | ID系のメッセージ（`法人IDはUUID v7である必要があります。`） |
| `field_name` | `BaseTelephoneNumber`（`ClassVar[str] = ""`） | TEL / FAX の区別（`FAX番号は0で始まる10桁または11桁の…`） |

```python
class CorporateId(EntityUUID):
    identifier_name = "法人ID"


class StoreFaxNumber(BaseTelephoneNumber):
    field_name = "FAX番号"
```

これ以外のプリミティブは、`validate()` の中に日本語のメッセージを直接書きます（`"店舗名は空にできません。"` など）。
`StaffQualification.label` や `BaseQualificationProfile.display_name` は資格の**画面表示名**であり、
エラーメッセージの項目名とは別の仕組みです。

### `kw_only` を付けない理由

`kw_only=True` は位置引数の取り違えを防ぐための指定です。Domain Primitive はフィールドが
`value` 1つだけなので取り違えようがなく、`value=` はクラス名が既に語っている情報の
繰り返しになるだけでした。そのため `DomainPrimitive` では指定しません。

フィールドが2つ以上になる概念は Domain Primitive ではなく Value Object です。そちらは
`kw_only=True` を維持します。`PersonName`（姓・名）や `ContactInfo`（電話・FAX）のように
**同じ型のフィールドが並ぶ**場合、順序の取り違えは型チェックを素通りするためです。

---

## 3. Value Object (値オブジェクト)

複数の Domain Primitive や基本型を組み合わせ、ドメイン概念を表現する複合オブジェクトです。

### 特徴
- **不変性**: `@dataclass(frozen=True, kw_only=True)` を付与し、状態変更を禁止します。
- **交換可能性**: 値の変更が必要な場合は新しいインスタンスに置き換えます。
- **等価性比較**: 保持する属性の値がすべて一致していれば同値とみなされます。
- **構成要素の型検証**: 共通 `ValueObject.__post_init__` が `_normalize_fields()`、MRO単位で解決した宣言型との照合、`validate()` の順に実行します。具象クラスは `__post_init__` を上書きしません。単純型・Enum・Optional・tuple・frozensetの内部まで照合し、違えば `DomainValidationError` を送出します。

### ファーストクラスコレクション

複数個の値をまとめて扱う概念は、リストを裸で持たずコレクション自体をValue Objectにします。
`StaffQualifications` は `tuple[BaseQualificationProfile, ...]` を包み、
「同一の資格区分が重複していないこと」を `validate()` で保証したうえで、
`get()` / `has()` / `from_profiles()` / `empty()` を提供します。

---

## 4. Domain Entity および Aggregate Root

識別子（ID）を持ち、時間経過とともに状態が変化するオブジェクトです。

### 特徴
- **同一性（Identity）**: 属性の値が変化しても、`id` が同じであれば同一のエンティティとして判定されます。
  `Entity.__eq__` は「同一クラスかつ同一ID」だけを見るため、**変更前後のインスタンスは等値になります**。
  値が変わったかを確かめたいときは `id` ではなくフィールドを比較してください。
- **基底クラスの適用**: `Entity[ID]` または `AggregateRoot[ID]` を継承し、`@dataclass(frozen=True, eq=False, kw_only=True)` を付与します。
- **共通初期化**: `Entity.__post_init__` もValue Objectと同じ順序で宣言型を照合し、具象集約による共通ガードの迂回を防ぎます。
- **不変（Immutable）**: 集約も frozen です。状態変更メソッドは `dataclasses.replace()` で
  **新しいインスタンスを返す**ので、呼び出し側は戻り値を受け直します。
- **ファクトリメソッド**: 新規作成時は `create()` メソッドを介して初期状態の不整合を防ぎます。IDは `XxxId.generate()` で採番します。
- **Aggregate Root (集約ルート)**: 外部（リポジトリやユースケース層）から直接取得・保存されるアクセスポイントです。
  集約内部の子エンティティは `Entity` を継承し、ルート経由でのみ操作します。
- **他集約への参照はIDのみ**: `Store` と `Patient` は `corporate_id` だけを持ち、`PatientCoverage` は `corporate_id` と `patient_id` だけを持ちます。Receptionの `CoverageSelectionRecord` も元資格IDと不変Snapshotだけを保持し、資格・Patient・StoreのAggregateを保持しません。参照先の実在性はID参照Protocolまたは永続化層の外部キー制約で担保します。
- **ドメインイベントは持たない**: `AggregateRoot` はイベントの記録・配送機構を意図的に持ちません。
  配送経路（`UnitOfWork` のコミット後にイベントを配送する仕組み）が無い状態でAPIだけ用意しても、
  消費されないリストが増えるだけだからです。必要になった時点で配送経路と併せて導入します。

```python
# 呼び出し側は必ず戻り値を受け直す
store = store.change_code(new_code)
await repository.save(store)
```

### `change_*` に同値チェックを置かない

状態変更メソッドは「変わっていないなら何もしない」判定を持たず、常に差し替えます。
同じ値を代入しても不変条件は壊れないため、これはドメインの制約ではなく
「保存を省けるか」という永続化の都合であり、Application層の関心だからです。

判定を両方に置くと、集約側の早期リターンはユースケースへ結果を伝えられないまま
（戻り値がない）二重に存在することになります。判定はユースケース側に一本化し、
「変更が無ければ保存しない」ことは Application層のテストで担保します。

### 導出プロパティ（状態を持たずに計算する）

現在値を専用フィールドとして持つのではなく、履歴から導出できるものは導出します。
`Staff` は主所属店舗・兼務店舗のフィールドを持たず、`affiliations`（`StoreAffiliation` のタプル）だけを保持し、
`current_home_store_id(today)` / `current_concurrent_store_ids(today)`
が対象日を受け取って計算します。

導出メソッドは**例外を送出しません**。所属期間の重なりは `Staff.validate()` が構築時に
禁止するため、対象日に有効な主所属は高々1件であることが保証されているからです。
読み取り時に検出する設計は、検出が遅れるうえ例外を期待しない呼び出し元へ漏れるため採りません。

---

## 5. Domain Service

エンティティや値オブジェクトの責務にするのが不自然なロジックや、複数の集約を跨ぐ業務ルールを記述します。

### 特徴
- **無状態（Stateless）**: インスタンス固有の状態を保持しません（依存するRepositoryのみコンストラクタで受け取ります）。
- **利用シーン**:
  - データベース問い合わせが必要な検証（例：名称の重複チェックなど）。
  - **複数集約間の相互作用・整合性チェック**（例：スタッフと店舗の法人一致検証など）。

### 現在のDomain Service

| クラス | 実装場所 | 役割 |
| :--- | :--- | :--- |
| `CorporateNameUniquenessService` | `app/domain/corporate/services.py` | 法人名の一意性（システム全体） |
| `StoreNameUniquenessService` | `app/domain/store/services.py` | 店舗名の一意性（法人単位） |
| `StoreCodeUniquenessService` | `app/domain/store/services.py` | 店舗コードの一意性（法人単位） |
| `InsurancePharmacyNumberUniquenessService` | `app/domain/store/services.py` | 保険薬局指定番号の一意性（システム全体） |
| `StaffCodeUniquenessService` | `app/domain/staff/services.py` | スタッフコードの一意性（法人単位） |
| `StaffStoreAssignmentService` | `app/domain/staff/services.py` | スタッフの配属・異動・兼務の調整（集約間） |
| `PatientCoverageConflictService` | `app/domain/coverage/services.py` | 同一患者・制度・順位の実効期間競合 |
| `CoverageSelectionService` | `app/domain/coverage/combination.py` | 明示された元資格IDから適用日の不変な選択投影を構築 |

一意性サービスは `ensure_*_is_unique(...)` を持ち、更新時は自分自身を `excluding_id` で除外します。

### 単一エンティティに収まらない（複数集約に跨る）場合の設計パターン

1. **なぜ単一エンティティに収めてはならないか？**
   - あるルール（例：「スタッフと店舗が同一法人に属しているか」）を `Staff` エンティティ内に持たせようとすると、`Staff` が別集約の `Store` エンティティを直接 `import` することになり、集約境界の独立性（識別子参照ルール）が破壊されます。
   - また、集約への直接依存を避けようとして `Staff.transfer_home_store(store_id, store_corporate_id=...)` のように個別の ID 群を引数として渡す設計にすると、「他法人の店舗IDに偽の自法人IDを添えて渡す」といった引数偽装攻撃・バグが生じた際に、エンティティ単体では実在する店舗IDと法人IDの正当な組み合わせを検証できません。

2. **ドメインサービスによる分離解決アプローチ**
   - **エンティティの責務（自集約の境界）**: `Staff` エンティティは他集約（`Store`）を知らず、`StoreId` と自集約の不変条件の維持に専念します。`Staff.validate()` が守るのは次の2つで、所属期間 `[start_date, end_date]`（`end_date=None` は無期限）の重なりとして判定します。
     1. `is_primary=True` の所属は、店舗を問わず互いに1日も重ならない（違反は `PrimaryAffiliationDuplicationError`）
     2. 同一 `store_id` の所属は、`is_primary` を問わず互いに1日も重ならない（違反は `ConcurrentStoreConflictError`）
   - **ドメインサービスの責務（集約間の調整役）**: 無状態なドメインサービス（`StaffStoreAssignmentService`）が、リポジトリ経由で正しくロードされた複数の本物集約オブジェクト（`Staff` と `Store`）を引数として受け取り、集約間の整合性（`store.corporate_id == staff.corporate_id`）を検証します。
   - 本物の `Store` オブジェクトを取り扱うことで偽装すり抜けが構造的に遮断され、安全性とDDDの集約境界保護が両立します。

3. **戻り値も新しい集約**
   - `StaffStoreAssignmentService` の `transfer_home_store()` / `assign_home_store()` / `assign_concurrent_store()` /
     `remove_concurrent_store()` は、いずれも更新後の `Staff` を返します。呼び出し側（ユースケース）が
     戻り値を受け取って `save()` します。

### 実装例

- **`CorporateNameUniquenessService`**:
  `CorporateRepository.exists_by_name()` を利用し、1つの `Corporate` だけでは判断できない法人名の一意性を検証します。更新時は自分自身の `CorporateId` を `excluding_id` として除外します。

- **`StaffStoreAssignmentService`**:
  `Staff` と `Store` の両オブジェクトを受け取り、法人一致を検証した上で所属履歴（`affiliations`）を組み替えた新しい `Staff` を返します。
  異動では「異動日より未来の主所属予約が無いこと」「異動日が現在の主所属開始日より後であること」を確認し、
  現在の主所属を異動日の前日で `close()` してから新しい主所属を追加します。

  **所属期間の重なり検証は本サービスが持ちません。** それは `Staff` 集約の責務であり、
  `replace()` の戻り値を組み立てた時点で `Staff.validate()` が拒否します。本サービスが担うのは
  集約間の整合（法人一致）と、集約単体では表現できない遷移ルール（未来の主所属予約との衝突、
  異動日と現主所属開始日の前後、解除対象の兼務行の存在）だけです。
  同じルールを両方に置くと、片方を壊しても誰も気づけません。

---

## 5.5 集約のライフサイクル表現（方言）

無効化の表し方は現在4通りに分かれています。`tests/domain/test_lifecycle_dialects.py`
がこの割り当てを凍結しており、表を編集しない限り pytest が落ちます。

| 方言 | 表現 | 該当する集約 |
| :--- | :--- | :--- |
| `none` | 無効化の概念を持たない | `Store`、`Patient`、`CoverageSelectionRecord` |
| `active_flag` | `is_active: bool` | `Staff`、`PatientExternalIdentifier` |
| `status_enum` | `status: CorporateStatus` | `Corporate` |
| `dated_activation` | `activation: CoverageActivation`（`[activated_on, deactivated_on)`） | `PatientCoverage` |

### なぜ統一しないか

`dated_activation` が最も表現力が高く、他の方言は「いつから無効か」を失います。
それでも今は統一しません。遡及判定を必要とする**到達可能なUseCaseが存在しない**からです。
AGENTS.md の「到達可能なClaim UseCaseがない間はClaim権限を定義しない」と同じ基準です。
`Store` の閉局・`Patient` の無効化も、要求元のユースケースが無いので追加しません。

### 統一に踏み切るトリガー

- **T1**: スタッフの店舗アクセス認可を行う到達可能なUseCaseが追加されたとき。
  `Staff.is_active` を `[employed_on, retired_on)` へ格上げする。
- **T2**: 過去日のレセプト再作成UseCaseが追加され、過去時点のスタッフ・店舗状態の
  再現が必要になったとき。
- **T3**: `dated_activation` が2集約目になったとき。`CoverageActivation` を
  Shared Kernel の汎用 `Activation` VO へ切り出す判断をここで行う。

### 一意キーの再利用可否

`active_flag` 方言の集約は、無効化後に一意キーを再利用できるかを**集約ごとに**決めます。
全称のルールにはしません（`Staff` に対して偽になるため）。判断は
`tests/domain/test_lifecycle_dialects.py` の `ACTIVE_FLAG_KEY_REUSE` に記録し、
実挙動は契約テストで固定します。判断を書かずに `is_active` を足すことはできません。

| 集約 | 再利用 | 理由 |
| :--- | :--- | :--- |
| `PatientExternalIdentifier` | 可 | 誤った患者へ紐付けた外部IDを無効化してから正しい患者へ付け替えるため |
| `Staff`（スタッフコード） | 不可 | 過去の調剤録・監査の追跡を壊さないため |

### 既知の限界

方言の分類はフィールド名と宣言型で行うため、まったく新しい語彙で既存集約に
無効化を実装すると `none` と分類され検出できません。新しい集約は表に行が無いので
必ず落ちるため、最大の穴（集約が増えるたびに方言が増える）は塞がっています。

---

## 6. ドメインモデル貧血症（Anemic Domain Model）の防止

ドメイン層を構築する際、単なるデータ構造（getter/setterのみのクラス）となり、ロジックがすべてユースケース層に流出する「ドメインモデル貧血症」を防止します。

1. **自己検証の徹底**: 入力データの形式チェックやビジネスルールの第一線ガードは Domain Primitive や Value Object で実施する。
2. **状態変更のカプセル化**: 外部から属性を直接書き換えるのではなく、意図を明確にしたドメインメソッド（例: `change_name()`, `deactivate()`）を介して状態を更新する。集約は frozen なので、そもそも直接代入はできない。
3. **データと振る舞いの一体化**: データに付随する計算や述語（判定ロジック）は、データを持つオブジェクト自体にプロパティやメソッドとして配置する（`PharmacistProfile.can_bill_insurance()`、`AffiliationPeriod.is_active_on()`、`AffiliationPeriod.overlaps()` など）。

---

## 7. Domain Repository

Domain Repositoryは、集約を永続化・再構築するための抽象です。実装はApplicationやInfrastructure側に置き、Domain層は`Protocol`だけに依存します。
現時点で存在する実装は `tests/fakes/` のインメモリRepositoryだけです。

各コンテキストは「通常のリクエスト経路で使う Repository」と「一覧・列挙用の Catalog Repository」の2本立てです。

### `CorporateRepository`

[`app/domain/corporate/repository.py`](../../app/domain/corporate/repository.py)

| 操作 | 役割 |
| :--- | :--- |
| `get(corporate_id)` | 指定IDの法人を取得する。存在しない場合は`None`を返す |
| `save(corporate)` | 法人を新規登録または変更保存する |
| `exists_by_name(name, *, excluding_id=None)` | 同名法人の存在を確認する。更新時は自分自身を除外できる |

### `StoreRepository`

[`app/domain/store/repository.py`](../../app/domain/store/repository.py)

| 操作 | 役割 |
| :--- | :--- |
| `get(store_id)` | 指定IDの店舗を取得する（**法人での絞り込みはしない**） |
| `save(store)` | 店舗を新規登録または変更保存する |
| `exists_by_name(*, corporate_id, name, excluding_id=None)` | 同一法人内の店舗名の重複を確認する |
| `exists_by_code(*, corporate_id, code, excluding_id=None)` | 同一法人内の店舗コードの重複を確認する |
| `exists_by_insurance_pharmacy_number(*, number, excluding_id=None)` | 保険薬局指定番号の重複を確認する（法人をまたぐ） |

### `StaffRepository`

[`app/domain/staff/repository.py`](../../app/domain/staff/repository.py)

| 操作 | 役割 |
| :--- | :--- |
| `get(*, corporate_id, staff_id)` | 指定法人内のスタッフを取得する。**他法人のデータには`None`を返すことを契約とする** |
| `save(staff)` | スタッフを新規登録または変更保存する |
| `exists_by_code(*, corporate_id, code, excluding_id=None)` | 同一法人内のスタッフコードの重複を確認する |

テナント境界の担保方法が店舗とスタッフで異なる点に注意してください。
店舗は `StoreRepository.get()` が法人を見ないため、Application層の `load_store_or_raise()` が
`store.corporate_id` を突き合わせます。スタッフは `StaffRepository.get()` 自体が `corporate_id` を要求します。

### `PatientRepository`

[`app/domain/patient/repository.py`](../../app/domain/patient/repository.py)

| 操作 | 役割 |
| :--- | :--- |
| `get(*, corporate_id, patient_id)` | 指定法人内の患者を取得する。他法人のデータや不存在は `None` を返す |
| `save(patient)` | 患者を新規登録または変更保存する |
| `allocate_patient_number(corporate_id)` | 法人単位で再利用しない患者番号を原子的に採番する |

`Patient` は `CorporateId` のみで所属法人を参照する独立した集約です。氏名は共有の
`PersonNames`、生年月日は任意の `PatientBirthDate`、法人内患者番号は不変の
`PatientNumber` で保持します。外部患者IDは `PatientExternalIdentifier` 別Aggregateで
連携先ごとに管理します。検索・名寄せ、無効化、削除、監査、処方箋はこの実装の責務に含めません。

### `PatientExternalIdentifierRepository`

患者と外部システムのID対応を管理します。同一法人・同一連携先・同一外部患者IDの組は
一意とし、無効化して履歴を残します。別の連携先のIDは同じ患者に複数登録できます。

一意性を要求するのは**有効な対応付け**に対してだけです。`get_active_by_source()` は有効行だけを
返すため、無効行の格納順に重複判定が左右されません。`save()` は同じ集約IDを除外した上で、
同一法人・連携先・外部患者IDの有効行を原子的に一意にする最終防衛契約を持ちます。無効化済みの
行まで衝突扱いにすると、誤紐付けを無効化した後に正しい患者へ付け替えられなくなるためです。

### `PatientCoverageRepository`

[`app/domain/coverage/repository.py`](../../app/domain/coverage/repository.py)

| 操作 | 役割 |
| :--- | :--- |
| `get(*, corporate_id, coverage_id)` | 指定法人の患者資格を取得する。別法人・不存在は `None` |
| `list_by_patient(*, corporate_id, patient_id)` | 指定法人・患者の資格履歴を取得する |
| `save(coverage)` | 実効期間の競合を原子的に拒否し、患者資格を新規登録または変更保存する |

`PatientCoverage` は資格種別、制度別詳細、制度期間、有効化区間、優先順位を持つ独立した
Aggregateです。医療保険は適用順位を1に固定し、同一患者・同一期間に複数の保険を置きません。
公費は第一から第四までの順位を持ち、同じ順位の実効期間重複だけを
`PatientCoverageConflictService` で拒否します。そのため、同一期間の医療保険1件と第一公費・
第二公費を併用できます。医療保険の一意性は順位固定により「同一制度かつ同一順位」の判定へ
含まれるため、競合サービス側で `coverage_type` を別途分岐させません（分岐させても結果は
変わらず、同じ規則が2箇所に分散します）。

制度期間 `CoveragePeriod` は終了日を含む `[valid_from, valid_to]`、台帳行の
`CoverageActivation` は無効化発効日を含まない `[activated_on, deactivated_on)` です。
実効期間は両者の交差です。無効化発効日当日は無効で、同日再無効化だけを冪等として許可し、
異なる発効日への変更は `CoverageDeactivationAlreadyFixedError` で拒否します。日付型の検証
（`datetime` の誤混入を含む）は `BaseDate` から受け継ぎます。レセプトで桁数が定まる番号は桁数をプリミティブの
不変条件として持たせます（`InsurerNumber` は6桁または8桁、`PublicPayerNumber` は8桁、
`PublicRecipientNumber` は7桁、`CoverageBranchNumber` は2桁）。桁数規定のない被保険者記号・
番号は `CoverageSymbol` / `CoverageCode` として空でないことだけを要求します。

`CoverageSelectionService` は明示された患者資格IDを本物のAggregateで検証し、Aggregateを保持しない
`CoverageCombination`（元IDと不変値の投影）を返します。別法人・別患者・適用日範囲外・重複ID・
未取得ID・医療保険複数・公費順位の重複／欠番を拒否します。請求時点の固定値はClaim側の
`CoverageSnapshot` として保存し、現在の資格変更によって過去の固定値を変化させません。

### `CoverageSelectionRecordRepository`

[`app/domain/reception/repository.py`](../../app/domain/reception/repository.py)

| 操作 | 役割 |
| :--- | :--- |
| `save(record)` | 受付時点の選択履歴を保存する。履歴なので複数行を許可する |
| `get_latest(*, corporate_id, store_id, patient_id)` | `(recorded_at, id)` の降順で最新履歴を取得する |

`CoverageSelectionRecord` は `corporate_id`、`store_id`、`patient_id`、業務上の適用日、
`CoverageSelection`、UTC記録時刻、記録者を持ちます。

`CoverageSelection` は医療保険枠0〜1個と公費枠0〜4個からなり、各枠が選択元資格IDと
請求固定値を**分離不能に1対1**で束ねます。以前は「元ID列」と「Snapshot」を並列の
2フィールドで持ち、対応は「医療保険 → 公費順位順」という並び順の規約でした。
件数一致しか検証できず、順序が入れ替わった履歴も構築できたためです。

対応を型で表せなかったのは、`CoverageSnapshot` が元IDを持たず `SourceCoverageId` も
素のUUIDで、集約内に照合材料が存在しなかったからです。そこで検証を足すのではなく
型の形を変えました。結果として「医療保険IDが先頭でない」「公費IDが順位とズレる」
「件数が合わない」という状態がそもそも表現できなくなり、`validate()` の件数照合は
**不要になって消えました**。検証を1本増やすのではなく1本消せることが、規約から
仕組みへ移行できた証拠です。VOが拒否するのは元資格IDの重複だけです。

`record.snapshot` と `record.source_coverage_ids` は枠構造からの導出 property であり、
独立した記憶域を持ちません。永続化実装を入れるときも `selection` だけをマップし、
この2つを列として持たせてはいけません（平坦化した2フィールドの再来になります）。

集約が守れるのは枠構造の一致までです。「その元IDが本当にその資格を指すか」は台帳を
引かないと判定できず、`CoverageValidityBoundary` の再検証の仕事として残ります。`CoverageSnapshot` は医療保険0〜1件と公費0〜4件を値として
固定します。医療保険1件と公費2件のような組み合わせも、公費順位を保持したまま保存できます。
公費の順位は第一公費から連続していなければならず、第一公費が空で第三公費だけを持つ組み合わせは
`CoverageCombinationInvalidError` として拒否します（レセプト提出時に返戻されるため、
凍結前に弾きます）。この順位規則（上限4件・重複なし・第一公費から連続）の実装は
Shared Kernel の `app/base/domain/priority_rules.py` に**1つだけ**あります。資格台帳側の
`CoverageCombination` と請求側の `CoverageSnapshot` は役割が違うので検証点は2つ残しますが、
規則そのものを2箇所に書くと片方だけ直る事故が起きるためです。各コンテキストは
`PriorityViolation` を自分の例外型とメッセージへ対応づけるだけにします。医療保険の `benefit_ratio` は必須です。給付割合は患者負担額を決める値であり、
スナップショットが存在する目的そのものなので、資格台帳の `InsuranceCoverageDetails` と
必須性を揃えます。元の資格台帳を後から参照して過去の値を再構成する設計にはしません。
最新履歴は受付画面の初期候補であり、今回の適用日で元IDの全資格を再ロードし、同じDomain Serviceで
正規化ID列とSnapshotを再構築した後にだけ利用します。結果は
`LastCoverageSelectionCandidateDto.is_still_valid` として返します。`CoverageRecordedAt` はaware
datetimeだけを受け入れてUTCへ正規化します。`DomainPrimitive.__post_init__()` は値の等価性に
かかわらず正規化値を必ず保持するため、同じ瞬間を表すJST入力もUTC表現で保存されます。

外部患者IDと患者資格の原子的競合拒否はRepository契約ですが、現時点では本番永続化実装が
ありません。Fakeの検証は本番DB制約の代替ではなく、部分一意索引・期間除外制約・別トランザクション
統合テストが追加されるまで `RESIDUAL-RISK-DB-01` は未解決です。

### `save()` という名前

`save()`は新規登録と変更保存の両方を表します。以前の`add()`のように新規登録だけを想起させる名前にせず、集約の保存という意図を明確にします。
実装側の責務（永続化層で満たすべき制約）は各 `save()` の docstring に明記しています。

### `XxxCatalogRepository`

`CorporateCatalogRepository` / `StoreCatalogRepository` / `StaffCatalogRepository` は、一覧・列挙のための別インターフェースです。

- `list_by_corporate_id(corporate_id)` — 法人単位の一覧（`Store` / `Staff` のみ。Patientの一覧・検索は未実装）
- `list_all()` — システム全体の列挙。起動時の補完や特権バッチ用で、**通常のリクエスト経路から使うとテナント境界を越える**ため使わない

## 8. Corporateコンテキストの実装

現在の法人ドメインは、次の集約と値オブジェクトで構成されています。

| 要素 | 実装 | 役割 |
| :--- | :--- | :--- |
| Aggregate Root | `Corporate` | 法人の状態と変更操作をまとめるマルチテナント境界 |
| Entity ID | `CorporateId` | UUIDv7による法人の識別子 |
| Enum | `CorporateStatus` | 法人の利用状態（`ACTIVE` / `INACTIVE`） |
| Value Object | `CorporateName` | 正規化済みの法人名。空文字を許可せず、100文字以内 |
| Value Object | `CorporateRepresentativeName` | `PersonName`を基底とする代表者名 |
| Domain Exception | `CorporateNameAlreadyExistsError` | 同名法人を拒否するためのドメイン例外 |

### `Corporate`の振る舞い

- `Corporate.create()`で新規法人を生成する。IDは`CorporateId.generate()`で採番する。
- `change_name()`で法人名を変更し、**変更後の新しい`Corporate`を返す**。
- `change_representative()`で代表者名を変更し、同じく新しい`Corporate`を返す。
- `activate()` / `deactivate()`で法人の利用状態を変更し、新しい`Corporate`を返す。通常の店舗・スタッフ操作で無効法人を拒否する判定と、ベンダー管理者だけに状態変更を許可する判定はApplication層が担当する。
- 外部から属性を直接変更せず、これらの意図を持ったメソッドを通して状態を変更する。
- 同値かどうかの判定は集約側では行わない。`ChangeCorporateNameUseCase` / `ChangeRepresentativeUseCase` が
  現在値と比較し、等しければ保存せずに戻る。

集約の不変条件に関わる値の検証は、`CorporateName`や`CorporateRepresentativeName`などのValue Object生成時に行います。複数の法人を参照する一意性は、`CorporateNameUniquenessService`と永続化層の制約で扱います。

Store・Staffコンテキストの構成要素の一覧は、[ナレッジベースの実装マップ](../index.md#現在の実装マップ)を参照してください。

## 9. Shared Kernelとの関係

各コンテキストは、`app/base/domain/`のShared Kernelを利用します。

- `DomainPrimitive[T]`: 不変・正規化・バリデーションを共通化する基底クラス
- `Entity[ID]`: IDによる同一性を提供する基底クラス
- `AggregateRoot[ID]`: Repositoryから直接扱う集約ルートの基底クラス
- `DomainError` / `DomainValidationError`: ドメイン例外の基底と入力検証エラー
- `EntityUUID` / `EntityStringId`: 識別子の基底。前者はUUIDv7を強制し、後者は「空でない文字列」だけを要求する
- `BasePersonName` / `BasePersonNameKana`: 人名・フリガナのプリミティブ（カナはNFKCで半角→全角に正規化）
- `PersonName` / `PersonNameKana` / `PersonNames`: 姓名、フリガナ、およびその一式を表すValue Object

Shared Kernelは3つ以上のコンテキストから参照される汎用的なルールに限定し、コンテキスト固有のルールは`app/domain/<context>/`へ置きます。

## 10. Domain層のテスト

Domain層では、実際の集約・Value Object・インメモリRepositoryを使って振る舞いを検証します。

| ファイル | 対象 |
| :--- | :--- |
| `tests/domain/corporate/test_corporate.py` | `Corporate`、値オブジェクト、ID、Repository契約の振る舞い |
| `tests/domain/corporate/test_corporate_services.py` | `CorporateNameUniquenessService` |
| `tests/domain/store/test_store.py` | `Store`の生成と各`change_*` |
| `tests/domain/store/test_store_primitives.py` | 店舗のプリミティブ・複合VOの境界値と不正値 |
| `tests/domain/store/test_store_services.py` | 店舗の各一意性サービス |
| `tests/domain/staff/test_staff.py` | `Staff`の生成、資格、所属の導出メソッド |
| `tests/domain/staff/test_staff_repository.py` | `StaffRepository`契約（法人境界を含む） |
| `tests/domain/staff/test_staff_services.py` | `StaffCodeUniquenessService`、`StaffStoreAssignmentService` |
| `tests/domain/test_person_names.py` | Shared Kernelの人名Value Object |
| `tests/domain/test_error_messages.py` | 例外クラスの既定メッセージ |

代表的な検証観点は次のとおりです。

- `create()`がUUIDv7のIDと正規化済みの値を生成すること
- 各プリミティブが不正値（空文字、最大長超過、フォーマット違反）を拒否すること
- `change_*`が新しいインスタンスを返し、元のインスタンスが変わらないこと
- Repositoryが保存・取得・更新・重複拒否を行うこと
- 一意性サービスが新規値を許可し、重複値を拒否すること
- `StaffStoreAssignmentService`が別法人の店舗割り当てと日付の矛盾を拒否すること

Domain層のテストでは、集約やValue Objectをモックしません。実際のオブジェクトを使い、ドメインモデルが期待どおりに状態を守ることを確認します。
Application層の処理順序やDTO変換は、`tests/application/`で別に検証します。

---
