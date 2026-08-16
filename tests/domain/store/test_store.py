"""店舗集約（Store）の振る舞いのテスト。"""

from __future__ import annotations

from dataclasses import replace

from app.domain.corporate import CorporateId
from app.domain.store import Store, StoreCode, StoreId
from tests.factories.store_factory import (
    VALID_INSURANCE_NUMBER,
    create_contact_info,
    create_store,
    create_store_address,
    create_store_names,
)


def test_create_generates_uuid7_and_keeps_optional_fields_unset() -> None:
    # Arrange
    corporate_id = CorporateId.generate()

    # Act
    store = Store.create(
        corporate_id=corporate_id,
        names=create_store_names(),
        address=create_store_address(),
        contact_info=create_contact_info(),
    )

    # Assert
    assert store.id.value.version == 7
    assert store.corporate_id == corporate_id
    assert store.code is None
    assert store.insurance_pharmacy_number is None


def test_create_assigns_a_new_id_for_each_store() -> None:
    # Arrange / Act
    first = create_store()
    second = create_store()

    # Assert
    assert first.id != second.id


def test_change_names_replaces_all_name_fields() -> None:
    # Arrange
    store = create_store()
    new_names = create_store_names(
        name="変更後薬局",
        kana="ヘンコウゴヤッキョク",
        romaji="Henkougo Pharmacy",
    )

    # Act
    store = store.change_names(new_names)

    # Assert
    assert store.names == new_names
    assert store.names.romaji is not None
    assert store.names.romaji.value == "Henkougo Pharmacy"


def test_change_address_replaces_address() -> None:
    # Arrange
    store = create_store()
    new_address = create_store_address(
        postal_code="5300001", address="大阪府大阪市北区梅田1-1-1"
    )

    # Act
    store = store.change_address(new_address)

    # Assert
    assert store.address == new_address
    assert store.address.postal_code.value == "530-0001"


def test_change_contact_info_replaces_contact_info() -> None:
    # Arrange
    store = create_store()
    new_contact_info = create_contact_info(
        phone_number="0612345678",
        fax_number="0612345679",
        email="store@example.com",
    )

    # Act
    store = store.change_contact_info(new_contact_info)

    # Assert
    assert store.contact_info == new_contact_info


def test_change_code_sets_and_clears_code() -> None:
    # Arrange
    store = create_store()
    new_code = StoreCode("ST-001")

    # Act
    store = store.change_code(new_code)

    # Assert
    assert store.code == new_code

    # Act: 解除
    store = store.change_code(None)

    # Assert
    assert store.code is None


def test_change_insurance_pharmacy_number_sets_and_clears_number() -> None:
    # Arrange
    store = create_store(insurance_pharmacy_number=VALID_INSURANCE_NUMBER)

    # Act
    store = store.change_insurance_pharmacy_number(None)

    # Assert
    assert store.insurance_pharmacy_number is None


def test_change_names_with_same_value_keeps_state() -> None:
    # Arrange: 集約は同値かどうかを判定せず、常に差し替える（保存要否はユースケースの関心）
    store = create_store()
    same_names = create_store_names()

    # Act
    store = store.change_names(same_names)

    # Assert
    assert store.names == same_names


def test_stores_with_same_id_are_equal_even_when_attributes_differ() -> None:
    # Arrange: 同一性はIDだけで決まることを確認する
    store = create_store(name="サンプル薬局")
    same_identity = create_store(name="別名薬局")
    same_identity = replace(same_identity, id=store.id)

    # Act / Assert
    assert store == same_identity
    assert hash(store) == hash(same_identity)


def test_stores_with_different_ids_are_not_equal() -> None:
    # Arrange
    first = create_store()
    second = create_store()

    # Act / Assert
    assert first != second


def test_store_is_not_equal_to_non_entity_object() -> None:
    # Arrange
    store = create_store()

    # Act / Assert
    assert store != StoreId.generate()
