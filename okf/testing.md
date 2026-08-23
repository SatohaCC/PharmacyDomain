---
type: Guideline
title: テスト層の実装ガイドライン
description: PharmacyDomain における AAA パターン、テスト分割、テストダブル、非同期テストの方針。
tags: [backend, testing, pytest, aaa, ddd]
timestamp: 2026-08-15T00:00:00Z
---

# テスト層の実装ガイドライン

PharmacyDomainのテストでは、テストの意図を明確にするため、古典学派のAAAパターンを基本とします。

- **Arrange**: テスト対象と入力、依存オブジェクトを準備する
- **Act**: テスト対象の振る舞いを1つ実行する
- **Assert**: 結果の状態、戻り値、例外を検証する

1つのテストでは、1つの振る舞いを検証します。テストを読む人が、何を準備し、何を実行し、何を期待しているかを追えることを重視します。

## 1. AAAパターン

### 1.1 Arrange

Arrangeでは、テストの前提条件をすべて準備します。

- Repositoryやテスト対象のUseCaseを生成する
- `Corporate`、`CorporateName`などの実際のドメインオブジェクトを生成する
- Command DTOを生成する
- 重複データや既存データをRepositoryへ保存する

Arrangeで作った値は、テストの前提を表す名前を付けます。`obj`や`data`のような曖昧な名前は避けます。

### 1.2 Act

Actでは、テスト対象の公開された振る舞いを1つだけ実行します。

```python
# Act
corporate_id = await use_case.execute(command)
```

非同期処理では、必ず`await`して実際の処理結果を取得します。Actの前後に別の業務操作を混ぜないでください。

例外を検証する場合は、例外が発生する操作を`pytest.raises`の中に置きます。

```python
# Act
with pytest.raises(CorporateNameAlreadyExistsError):
    await use_case.execute(command)
```

### 1.3 Assert

Assertでは、利用者から見える結果を検証します。

- 戻り値の値や型
- Repositoryへ保存された状態
- 状態変更後に再取得した集約の値
- 期待した例外の型と必要なメッセージ
- 失敗時に不要なデータが保存されていないこと
- 変更が無い場合に保存が行われていないこと（Fakeの`save_count`）

実装内部のローカル変数やprivate属性ではなく、公開された結果と副作用を検証します。

集約は不変（frozen）なので、変更を確認するときは元のインスタンスではなく
**Repositoryから再取得した集約**、または`change_*`の戻り値を検証します。
`Entity.__eq__`は型と`id`だけで判定するため、`assert before != after`のような比較は成立しません。

## 2. テストの基本テンプレート

```python
async def test_register_corporate_returns_id_and_persists_corporate() -> None:
    # Arrange
    repository = InMemoryCorporateRepository()
    use_case = create_use_case(repository)
    command = create_command()

    # Act
    corporate_id = await use_case.execute(command)

    # Assert
    actual = await repository.get(corporate_id)
    assert actual is not None
    assert actual.name.value == command.name
```

コメントは必須ではありませんが、AAAの境界が読み取りづらいテストでは明示します。Arrange用のヘルパーは、テストの意図を隠さない範囲で使用します。

## 3. テストの分割

### 3.1 Domain層

実装場所: `tests/domain/`

Domain層では、ドメインモデルのルールと振る舞いを検証します。

| ファイル | 対象 |
| :--- | :--- |
| `corporate/test_corporate.py` | `Corporate`、値オブジェクト、ID、Repository契約の振る舞い |
| `corporate/test_corporate_services.py` | `CorporateNameUniquenessService` |
| `store/test_store.py` | `Store`の生成と各`change_*` |
| `store/test_store_primitives.py` | 店舗のプリミティブ・複合VOの境界値と不正値 |
| `store/test_store_services.py` | 店舗名・店舗コード・保険薬局指定番号の一意性サービス |
| `staff/test_staff.py` | `Staff`の生成、資格、所属の導出メソッド |
| `staff/test_staff_repository.py` | `StaffRepository`契約（法人境界を含む） |
| `staff/test_staff_services.py` | `StaffCodeUniquenessService`、`StaffStoreAssignmentService` |
| `coverage/` | 資格の制度期間・有効化区間・競合・選択組み合わせ |
| `reception/` | 選択履歴の元ID・監査値・最新順の不変条件 |
| `test_field_guard.py` | Composite Value Object / Entityの宣言型と実値の照合 |
| `test_person_names.py` | Shared Kernelの人名Value Object |
| `test_error_messages.py` | 例外クラスの既定メッセージ |

Domain層のテストでは、集約やValue Objectをモックしません。実際のオブジェクトを使い、ドメインモデルが期待どおりに状態を守ることを確認します。

### 3.2 Application層

実装場所: `tests/application/`

Application層では、Commandの変換、ユースケースの処理順序、Repositoryとの連携、DTO変換、テナント境界を検証します。

| ディレクトリ | ファイル |
| :--- | :--- |
| `corporate/` | `test_register_corporate.py`、`test_change_corporate_name.py`、`test_change_representative.py`、`test_get_corporate.py` |
| `store/` | `test_register_store.py`、`test_change_store_name.py`、`test_change_store_code.py`、`test_change_store_address.py`、`test_change_store_contact_info.py`、`test_change_insurance_pharmacy_number.py`、`test_get_store.py`、`test_list_stores.py`、`test_change_skips_save.py` |
| `staff/` | `test_register_staff.py`、`test_change_staff_names.py`、`test_update_qualifications.py`、`test_deactivate_staff.py`、`test_transfer_home_store.py`、`test_get_staff.py`、`test_list_staffs.py` |
| `coverage/` | 資格の登録・取得・一覧・制度期間変更・発効日付き無効化 |
| `reception/` | 資格選択の登録、最新候補、Actor/Clock監査、Tenant境界 |
| `composition/` | 実 `CoverageSelectionAdapter` と `SystemUtcClock` |

Application層のテストは、ユースケースごとにファイルを分けます。共通の集約生成処理は`helpers.py`（`corporate/` と `store/`）や`tests/factories/`へ切り出し、テスト本体の責務と準備処理を分離します。

`store/test_change_skips_save.py`は、変更が無いときに`save()`を呼ばないことを`save_count`で横断的に検証する専用ファイルです。

現時点で `ActivateStaffUseCase`、`ChangeStaffJobTitleUseCase`、`AssignStaffConcurrentStoreUseCase`、
`RemoveStaffConcurrentStoreUseCase` には専用のテストファイルがありません。追加する際は上記の分割に従います。

Application層でも、インメモリRepositoryを使い、ドメインモデルとRepositoryの実際の振る舞いを組み合わせて確認します。

### 3.3 テスト用Repository（Fake）

`tests/fakes/` のインメモリRepositoryは、実装するProtocolごとの最終防衛契約を再現します。

| ファイル | クラス | 実装するProtocol |
| :--- | :--- | :--- |
| `in_memory_corporate_repository.py` | `InMemoryCorporateRepository` | `CorporateRepository`、`CorporateCatalogRepository` |
| `in_memory_store_repository.py` | `InMemoryStoreRepository` | `StoreRepository`、`StoreCatalogRepository` |
| `in_memory_staff_repository.py` | `InMemoryStaffRepository` | `StaffRepository`、`StaffCatalogRepository` |
| `in_memory_patient_repository.py` | 患者・外部患者IDRepository | 患者境界、有効な外部IDの原子的な一意性 |
| `in_memory_patient_coverage_repository.py` | `InMemoryPatientCoverageRepository` | 実効期間の原子的な競合拒否 |
| `in_memory_coverage_selection_record_repository.py` | `InMemoryCoverageSelectionRecordRepository` | 複数履歴の保存と `(recorded_at, id)` 最新順 |

共通する性質は次のとおりです。

- 一意性を持つRepositoryの`save()`だけが競合を最終検証し、本番永続化層と同じドメイン例外を送出する
- 履歴Repositoryは複数行を許可し、不要な一意性検証を追加しない
- `save_count`は保存回数を検証するFakeだけに持たせる
- `get()`と`list_*()`ではdeep copyを返し、永続化層に近い分離を再現する
- `InMemoryStaffRepository.get()`は`corporate_id`が一致しない場合に`None`を返し、Protocolの法人境界の契約を守る
- データベースやネットワークに依存しない

Fakeは、テストに必要な現実的な振る舞いを持たせます。単にメソッドが呼ばれたことだけを確認するMockとは目的が異なります。
外部患者IDと患者資格のFakeには、両タスクが事前readを終えてからsaveへ進める同期フックを置き、
read-check-writeの競合でも片方だけが成功することを決定的に検証します。ただしFakeが成功しても
本番DBの原子性は保証されません。部分一意索引・期間除外制約・別トランザクション統合テストが
揃うまで `RESIDUAL-RISK-DB-01` は未解決です。

### 3.4 ファクトリ

`tests/factories/` には、フィールドの多い集約を既定値付きで組み立てるヘルパーがあります。

- `store_factory.py` — `Store`の組み立て
- `staff_factory.py` — `create_person_names()` と `create_staff()`

いずれも永続化はせず、集約を返すだけです。保存が必要な場合は各ディレクトリの`helpers.py`（`save_corporate()` / `save_store()`）を使います。

## 4. テスト名

テスト名は、対象・条件・期待結果が分かる形式にします。

```text
test_<対象>_<条件>_<期待結果>
```

現在の例:

- `test_register_corporate_returns_id_and_persists_corporate`
- `test_register_corporate_rejects_duplicate_name_without_second_record`
- `test_change_corporate_name_rejects_another_corporates_name`
- `test_get_corporate_raises_when_corporate_does_not_exist`
- `test_change_names_replaces_all_name_fields`
- `test_transfer_home_store_raises_error_when_future_primary_affiliation_exists`

テスト名だけで失敗理由が推測できるようにし、`test_success`や`test_invalid`のような曖昧な名前は避けます。

## 5. 例外と境界値

### 5.1 例外

例外は、型を検証したうえで、利用者にとって意味のあるメッセージが契約の一部である場合だけメッセージも検証します。

```python
with pytest.raises(CorporateNameAlreadyExistsError) as exc_info:
    await service.ensure_name_is_unique(name=existing_name)

assert f"法人名 '{existing_name.value}' は既に登録されています。" in str(exc_info.value)
```

例外クラスの既定メッセージそのものは、`tests/domain/test_error_messages.py`が`parametrize`で一括検証しています。

### 5.2 境界値

Domain PrimitiveやValue Objectのテストでは、正常値だけでなく境界値と不正値を確認します。

- 空文字、空白だけの文字列
- 最大長を超える文字列
- 無効なUUIDやUUIDv7以外のUUID
- Composite dataclassへ渡す生文字列、生`date`、tuple内の誤型
- `date`フィールドへの`datetime`、`int`フィールドへの`bool`
- 姓または名だけが空の代表者名
- フォーマット違反（カナ以外の店舗名カナ、桁数違いの電話番号、都道府県コードや調剤区分が不正な保険薬局指定番号など）
- 同一値への変更

同じルールに対して入力だけが異なる場合は、`pytest.mark.parametrize`を使ってテストの重複を減らします。

## 6. テストの独立性

- テスト間でRepositoryや集約を共有しない
- 各テストでArrangeを完結させる
- 実行順序に依存しない
- 現在時刻、乱数、UUIDなどに依存する場合は、公開された契約を通して検証する。Receptionの記録時刻は`FakeClock`を注入する
- 日付に依存するドメイン（スタッフ所属・患者資格）では、`date.today()`任せにせず対象日を明示的に渡す
- 外部データベースやネットワークを単体テストから呼び出さない

テストの失敗が別のテストの実行結果に影響しないことを優先します。

## 7. 非同期テスト

`pyproject.toml`で`asyncio_mode = "auto"`と`asyncio_default_fixture_loop_scope = "function"`を設定しているため、
`async def test_*` は`@pytest.mark.asyncio`が無くても実行されます。

現状は法人・スタッフのテストがマーカーを明示し、店舗のテストは省略しています。どちらでも動作しますが、
1ファイル内では書き方を揃えてください。

```python
@pytest.mark.asyncio
async def test_change_representative_updates_and_persists_corporate() -> None:
    # Arrange
    ...

    # Act
    await use_case.execute(command)

    # Assert
    ...
```

## 8. 避けるテスト

- Arrange / Act / Assertが混ざっていて、テストの流れが追えないテスト
- 1つのテストで複数の業務操作を検証するテスト
- DomainモデルをMockして、Domainモデルの振る舞いを検証してしまうテスト
- private属性や実装上の呼び出し回数だけを検証するテスト
- 成功ケースだけで、重複・未存在・不正入力を確認しないテスト
- テスト間で状態を共有するテスト
- 例外を広すぎる`Exception`で受けるテスト
- `change_*`の戻り値を使わず、変更前のインスタンスを検証してしまうテスト

## 9. 実行コマンド

```bash
# 全テスト
uv run pytest -q

# Domain層だけ
uv run pytest -q tests/domain

# Application層だけ
uv run pytest -q tests/application

# 単体
uv run pytest -q tests/domain/store/test_store.py::test_change_names_replaces_all_name_fields

# 型チェック・lint
uv run mypy app tests
uv run ruff check .
uv run ruff format --check .
```

テスト追加後は、対象テストだけでなく全テストを実行し、既存の振る舞いを壊していないことを確認します。
