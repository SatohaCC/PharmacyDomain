"""医薬品マスタと処方箋の規制判定をつなぐ実アダプタ（腐敗防止層）。

`MedicineRestrictionBoundary`（Prescription が要求する形）を、
`MedicineCatalogRepository`（薬価基準の生の事実）から満たす。

**両者の形が違うことが要点である。** マスタが持つのは剤形・効能・麻薬区分と
いった事実で、処方箋が要るのは「リフィル適用除外か」という規則の答えである。
この変換をどちらかの内側へ寄せると、薬価基準にリフィルの規則が混ざるか、
処方箋が薬価基準のカラム構成を知ることになる。Composition に閉じ込める。
"""

from __future__ import annotations

from datetime import date

from app.application.prescription.reference import MedicineRestrictionBoundary
from app.base.domain.medicine import MedicineIdentifier
from app.domain.medicine_catalog.medicine import Medicine
from app.domain.medicine_catalog.repository import MedicineCatalogRepository
from app.domain.prescription.value_objects import (
    MedicineClassification,
    MedicineRestrictionFlag,
)


class MedicineCatalogRestrictionAdapter(MedicineRestrictionBoundary):
    """医薬品マスタから処方箋向けの規制区分を組み立てる。"""

    def __init__(self, repository: MedicineCatalogRepository) -> None:
        self._repository = repository

    async def classify(
        self,
        *,
        identifiers: tuple[MedicineIdentifier, ...],
        as_of: date,
    ) -> dict[MedicineIdentifier, MedicineClassification]:
        """指定日に有効なマスタ行から規制区分を導出する。

        **マスタに無い薬品は戻り値へ含めない。** 呼び出し側の Domain Service が
        ``MedicineClassificationMissingError`` として拒否する。ここで
        「該当しない」既定値を埋めると、未収載の薬品で麻薬・リフィルの判定が
        静かに素通りする（``okf/log.md`` ADR-11）。

        ``UNKNOWN`` も返さない。マスタ行が引けた以上、そこに書かれた事実は
        確定しているためである。``UNKNOWN`` は「マスタが無い」ことではなく
        「マスタはあるが値が未確定」を表す値であり、この実装では起きない。
        """
        classified: dict[MedicineIdentifier, MedicineClassification] = {}
        for identifier in identifiers:
            medicine = await self._repository.find_effective(
                identifier=identifier, as_of=as_of
            )
            if medicine is None:
                continue
            classified[identifier] = _classify(identifier, medicine)
        return classified


def _classify(
    identifier: MedicineIdentifier, medicine: Medicine
) -> MedicineClassification:
    """マスタ行の事実を、処方箋が要求する規制区分へ写す。"""
    return MedicineClassification(
        identifier=identifier,
        is_narcotic=_flag(medicine.is_narcotic),
        has_dosage_limit=_flag(medicine.has_dosage_limit),
        is_refill_restricted_patch=_flag(medicine.is_refill_restricted_patch),
    )


def _flag(value: bool) -> MedicineRestrictionFlag:
    """真偽値を規制区分の値へ写す。"""
    return MedicineRestrictionFlag.YES if value else MedicineRestrictionFlag.NO
