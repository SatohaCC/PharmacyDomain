"""MedicationHistoryCategoryCatalog集約の単体テスト。"""

from __future__ import annotations

import pytest

from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    DuplicateMajorCategoryError,
    DuplicateMediumCategoryError,
    MajorCategoryCode,
    MajorCategoryDefinition,
    MajorCategoryName,
    MajorCategoryNotFoundError,
    MedicationHistoryCategoryCatalog,
    MediumCategoryCode,
    MediumCategoryDefinition,
    MediumCategoryName,
    RequiredCategoryMissingError,
)
from app.domain.medication_history.primitives import CategoryCatalogId
from app.domain.medication_history.value_objects import SoapRecord
from tests.factories.medication_history_factory import (
    create_note,
    create_record,
)


def _sample_catalog(
    *,
    corporate_id: CorporateId | None = None,
    major_categories: tuple[MajorCategoryDefinition, ...] | None = None,
    medium_categories: tuple[MediumCategoryDefinition, ...] | None = None,
) -> MedicationHistoryCategoryCatalog:
    return MedicationHistoryCategoryCatalog(
        id=CategoryCatalogId.generate(),
        corporate_id=corporate_id or CorporateId.generate(),
        major_categories=major_categories
        if major_categories is not None
        else (
            MajorCategoryDefinition(
                code=MajorCategoryCode("soap"),
                name=MajorCategoryName("SOAP"),
                display_order=1,
            ),
        ),
        medium_categories=medium_categories
        if medium_categories is not None
        else (
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=MajorCategoryCode("soap"),
                name=MediumCategoryName("S（主観的情報）"),
                display_order=1,
            ),
        ),
    )


def test_create_default_catalog() -> None:
    """TC-CAT-01: デフォルト構築で標準の大区分・中区分が生成され紐づいていること。"""
    corp_id = CorporateId.generate()
    catalog = MedicationHistoryCategoryCatalog.create_default(corporate_id=corp_id)

    assert catalog.corporate_id == corp_id
    major_codes = [m.code.value for m in catalog.major_categories]
    assert "soap" in major_codes
    assert "statutory" in major_codes

    medium_codes = [m.code.value for m in catalog.medium_categories]
    for expected in (
        "s",
        "o",
        "a",
        "p",
        "handbook",
        "residual_drug",
        "concurrent_medication",
        "other",
    ):
        assert expected in medium_codes

    # 全ての中区分の親大区分が存在すること
    for med in catalog.medium_categories:
        assert med.major_category_code.value in major_codes


def test_duplicate_major_category_rejected() -> None:
    """TC-CAT-02: 同一コードの大区分重複が拒否されること。"""
    dup_code = MajorCategoryCode("soap")
    with pytest.raises(DuplicateMajorCategoryError):
        _sample_catalog(
            major_categories=(
                MajorCategoryDefinition(
                    code=dup_code, name=MajorCategoryName("SOAP 1"), display_order=1
                ),
                MajorCategoryDefinition(
                    code=dup_code, name=MajorCategoryName("SOAP 2"), display_order=2
                ),
            )
        )


def test_duplicate_medium_category_rejected() -> None:
    """TC-CAT-03: 同一コードの中区分重複が拒否されること。"""
    dup_code = MediumCategoryCode("s")
    major_code = MajorCategoryCode("soap")
    with pytest.raises(DuplicateMediumCategoryError):
        _sample_catalog(
            major_categories=(
                MajorCategoryDefinition(
                    code=major_code, name=MajorCategoryName("SOAP"), display_order=1
                ),
            ),
            medium_categories=(
                MediumCategoryDefinition(
                    code=dup_code,
                    major_category_code=major_code,
                    name=MediumCategoryName("S 1"),
                    display_order=1,
                ),
                MediumCategoryDefinition(
                    code=dup_code,
                    major_category_code=major_code,
                    name=MediumCategoryName("S 2"),
                    display_order=2,
                ),
            ),
        )


def test_unreferenced_major_category_rejected() -> None:
    """TC-CAT-04: 存在しない大区分コードを参照する中区分が拒否されること。"""
    with pytest.raises(MajorCategoryNotFoundError):
        _sample_catalog(
            major_categories=(
                MajorCategoryDefinition(
                    code=MajorCategoryCode("soap"),
                    name=MajorCategoryName("SOAP"),
                    display_order=1,
                ),
            ),
            medium_categories=(
                MediumCategoryDefinition(
                    code=MediumCategoryCode("other"),
                    major_category_code=MajorCategoryCode("non_existent"),
                    name=MediumCategoryName("その他"),
                    display_order=1,
                ),
            ),
        )


def test_add_and_update_major_category() -> None:
    """TC-CAT-05: 大区分の追加および更新ができること。"""
    catalog = _sample_catalog()
    custom_major = MajorCategoryDefinition(
        code=MajorCategoryCode("followup"),
        name=MajorCategoryName("フォローアップ"),
        display_order=2,
    )
    added = catalog.add_major_category(custom_major)
    assert len(added.major_categories) == len(catalog.major_categories) + 1
    assert any(m.code == custom_major.code for m in added.major_categories)

    # 更新
    updated_major = MajorCategoryDefinition(
        code=MajorCategoryCode("followup"),
        name=MajorCategoryName("調剤後フォロー"),
        display_order=3,
        is_enabled=False,
    )
    updated = added.update_major_category(updated_major)
    target = next(m for m in updated.major_categories if m.code == custom_major.code)
    assert target.name.value == "調剤後フォロー"
    assert target.display_order == 3
    assert not target.is_enabled


def test_add_and_update_medium_category() -> None:
    """TC-CAT-06: 中区分の追加および更新ができること。"""
    catalog = _sample_catalog()
    new_medium = MediumCategoryDefinition(
        code=MediumCategoryCode("p"),
        major_category_code=MajorCategoryCode("soap"),
        name=MediumCategoryName("P（計画）"),
        display_order=2,
        is_required=False,
    )
    added = catalog.add_medium_category(new_medium)
    assert any(m.code == new_medium.code for m in added.medium_categories)

    # 更新（必須フラグTrueへ）
    updated_medium = MediumCategoryDefinition(
        code=MediumCategoryCode("p"),
        major_category_code=MajorCategoryCode("soap"),
        name=MediumCategoryName("P（次回指導計画）"),
        display_order=2,
        is_required=True,
    )
    updated = added.update_medium_category(updated_medium)
    target = next(m for m in updated.medium_categories if m.code == new_medium.code)
    assert target.name.value == "P（次回指導計画）"
    assert target.is_required is True


def test_medium_categories_for_major() -> None:
    """TC-CAT-07: 大区分別の中区分が正しく抽出されること。"""
    soap_code = MajorCategoryCode("soap")
    statutory_code = MajorCategoryCode("statutory")
    catalog = _sample_catalog(
        major_categories=(
            MajorCategoryDefinition(
                code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
            ),
            MajorCategoryDefinition(
                code=statutory_code, name=MajorCategoryName("法令"), display_order=2
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S"),
                display_order=1,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("handbook"),
                major_category_code=statutory_code,
                name=MediumCategoryName("手帳"),
                display_order=2,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P"),
                display_order=3,
            ),
        ),
    )

    soap_mediums = catalog.medium_categories_for(soap_code)
    assert [m.code.value for m in soap_mediums] == ["s", "p"]


def test_required_medium_categories() -> None:
    """TC-CAT-08: 必須かつ有効な中区分が抽出されること。"""
    soap_code = MajorCategoryCode("soap")
    catalog = _sample_catalog(
        major_categories=(
            MajorCategoryDefinition(
                code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S"),
                display_order=1,
                is_required=True,
                is_enabled=True,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("o"),
                major_category_code=soap_code,
                name=MediumCategoryName("O"),
                display_order=2,
                is_required=False,
                is_enabled=True,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P"),
                display_order=3,
                is_required=True,
                is_enabled=False,  # 非アクティブは除外
            ),
        ),
    )

    reqs = catalog.required_medium_categories()
    assert [m.code.value for m in reqs] == ["s"]


def test_validate_record_compliance_success() -> None:
    """TC-CAT-09: 必須中区分を満たす薬歴が検証をパスすること。"""
    soap_code = MajorCategoryCode("soap")
    catalog = _sample_catalog(
        major_categories=(
            MajorCategoryDefinition(
                code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S"),
                display_order=1,
                is_required=True,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P"),
                display_order=2,
                is_required=True,
            ),
        ),
    )

    # SとPの両方に記載がある薬歴
    record = create_record(
        soap=SoapRecord(
            subjective=(create_note("S記載"),),
            plan=(create_note("P記載"),),
        )
    )

    # 例外なくパスする
    catalog.validate_record_compliance(record)


def test_validate_record_compliance_missing_required() -> None:
    """TC-CAT-10: 必須中区分が不足している薬歴で例外が送出されること。"""
    soap_code = MajorCategoryCode("soap")
    catalog = _sample_catalog(
        major_categories=(
            MajorCategoryDefinition(
                code=soap_code, name=MajorCategoryName("SOAP"), display_order=1
            ),
        ),
        medium_categories=(
            MediumCategoryDefinition(
                code=MediumCategoryCode("s"),
                major_category_code=soap_code,
                name=MediumCategoryName("S（主観的情報）"),
                display_order=1,
                is_required=True,
            ),
            MediumCategoryDefinition(
                code=MediumCategoryCode("p"),
                major_category_code=soap_code,
                name=MediumCategoryName("P（計画）"),
                display_order=2,
                is_required=True,
            ),
        ),
    )

    # SはあるがPが空の薬歴
    record = create_record(
        soap=SoapRecord(
            subjective=(create_note("S記載"),),
            plan=(),
        )
    )

    with pytest.raises(RequiredCategoryMissingError) as exc_info:
        catalog.validate_record_compliance(record)
    assert "P（計画）" in str(exc_info.value)
