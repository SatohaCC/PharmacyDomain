"""医薬品マスタテストで共有する組み立てヘルパー。"""

from __future__ import annotations

from datetime import date

from app.base.domain.medicine import (
    MedicineCode,
    MedicineCodeType,
    MedicineIdentifier,
    MedicineName,
    MedicineUnit,
)
from app.domain.medicine_catalog import (
    GenericCategory,
    Medicine,
    MedicineCatalogVersion,
    MedicineDosageForm,
    MedicineEffectivePeriod,
    MedicineListedOn,
    MedicineWithdrawnOn,
    NarcoticCategory,
)

LISTED_ON = date(2020, 4, 1)
CATALOG_VERSION = date(2026, 4, 1)
MEDICINE_CODE = "2171022F1029"
MEDICINE_NAME = "ノルバスク錠２．５ｍｇ"


def create_identifier(code: str = MEDICINE_CODE) -> MedicineIdentifier:
    """YJコードの薬品識別子を組み立てる。"""
    return MedicineIdentifier(code_type=MedicineCodeType.YJ, code=MedicineCode(code))


def create_period(
    listed_on: date = LISTED_ON, withdrawn_on: date | None = None
) -> MedicineEffectivePeriod:
    """収載期間を組み立てる。"""
    return MedicineEffectivePeriod(
        listed_on=MedicineListedOn(listed_on),
        withdrawn_on=(
            MedicineWithdrawnOn(withdrawn_on) if withdrawn_on is not None else None
        ),
    )


def create_medicine(
    *,
    code: str = MEDICINE_CODE,
    name: str = MEDICINE_NAME,
    unit: str = "錠",
    dosage_form: MedicineDosageForm = MedicineDosageForm.TABLET,
    listed_on: date = LISTED_ON,
    withdrawn_on: date | None = None,
    narcotic_category: NarcoticCategory = NarcoticCategory.NONE,
    generic_category: GenericCategory = GenericCategory.BRAND,
    has_dosage_limit: bool = False,
    is_analgesic_antiinflammatory: bool = False,
    is_dermatological: bool = False,
) -> Medicine:
    """マスタ行を1件組み立てる。"""
    return Medicine.register(
        identifier=create_identifier(code),
        name=MedicineName(name),
        unit=MedicineUnit(unit),
        effective_period=create_period(listed_on, withdrawn_on),
        catalog_version=MedicineCatalogVersion(CATALOG_VERSION),
        dosage_form=dosage_form,
        narcotic_category=narcotic_category,
        generic_category=generic_category,
        has_dosage_limit=has_dosage_limit,
        is_analgesic_antiinflammatory=is_analgesic_antiinflammatory,
        is_dermatological=is_dermatological,
    )


def create_refill_restricted_patch(
    *,
    narcotic_category: NarcoticCategory = NarcoticCategory.NONE,
    is_dermatological: bool = False,
) -> Medicine:
    """リフィル不可の貼付剤（鎮痛・消炎、麻薬でない、皮膚疾患用でない）を作る。

    除外条件を切り替えられるようにしてあるので、「麻薬の貼付剤は貼付剤の
    除外に当たらない」といった向きもこのファクトリで組み立てられる。
    """
    return create_medicine(
        code="2649729S1032",
        name="ロキソプロフェンＮａテープ１００ｍｇ",
        unit="枚",
        dosage_form=MedicineDosageForm.PATCH,
        is_analgesic_antiinflammatory=True,
        narcotic_category=narcotic_category,
        is_dermatological=is_dermatological,
    )
