"""医薬品マスタのリポジトリ一括保存（save_all）テスト (TC-24, TC-25)。"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.medicine_catalog.exceptions import MedicineEffectivePeriodConflictError
from app.domain.medicine_catalog.medicine import Medicine
from app.domain.medicine_catalog.primitives import MedicineDosageForm
from tests.factories.medicine_catalog_factory import create_medicine
from tests.fakes.in_memory_medicine_catalog_repository import (
    InMemoryMedicineCatalogRepository,
)


def _make_medicine(
    *,
    code: str,
    listed_on: date,
    withdrawn_on: date | None = None,
    name: str = "テスト医薬品",
) -> Medicine:
    """テスト用医薬品集約を生成する。"""
    return create_medicine(
        code=code,
        name=name,
        unit="錠",
        dosage_form=MedicineDosageForm.TABLET,
        listed_on=listed_on,
        withdrawn_on=withdrawn_on,
    )


@pytest.mark.asyncio
async def test_save_allで一括保存後に検索できる() -> None:
    """TC-24: InMemoryMedicineCatalogRepository.save_all で複数件が一括保存され find_effective で取得できる。"""
    repo = InMemoryMedicineCatalogRepository()
    med1 = _make_medicine(code="1111111F1011", listed_on=date(2020, 1, 1), name="薬品1")
    med2 = _make_medicine(code="2222222F2022", listed_on=date(2022, 1, 1), name="薬品2")

    await repo.save_all([med1, med2])

    found1 = await repo.find_effective(
        identifier=med1.identifier,
        as_of=date(2026, 1, 1),
    )
    found2 = await repo.find_effective(
        identifier=med2.identifier,
        as_of=date(2026, 1, 1),
    )
    assert found1 is not None
    assert found1.name.value == "薬品1"
    assert found2 is not None
    assert found2.name.value == "薬品2"


@pytest.mark.asyncio
async def test_save_allでも期間重複が原子的に拒否される() -> None:
    """TC-25: 同一薬品コードで期間が重複する2件を save_all に渡した場合、MedicineEffectivePeriodConflictError が発生する。"""
    repo = InMemoryMedicineCatalogRepository()
    # 同一コードで期間が重複する2件
    med1 = _make_medicine(
        code="1111111F1011",
        listed_on=date(2020, 1, 1),
        withdrawn_on=date(2024, 12, 31),
    )
    med2 = _make_medicine(
        code="1111111F1011",
        listed_on=date(2023, 1, 1),
        withdrawn_on=None,
    )

    with pytest.raises(MedicineEffectivePeriodConflictError):
        await repo.save_all([med1, med2])
