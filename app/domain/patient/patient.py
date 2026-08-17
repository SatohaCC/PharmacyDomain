"""患者集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.base.domain.value_object import PersonNames
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientBirthDate, PatientId, PatientNumber


@dataclass(frozen=True, eq=False, kw_only=True)
class Patient(AggregateRoot[PatientId]):
    """患者エンティティ（集約ルート）。法人単位で管理する患者情報を表す。"""

    id: PatientId
    corporate_id: CorporateId
    names: PersonNames
    patient_number: PatientNumber
    birth_date: PatientBirthDate | None = None

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        names: PersonNames,
        patient_number: PatientNumber,
        birth_date: PatientBirthDate | None = None,
    ) -> Self:
        """新しい患者を生成する。"""
        return cls(
            id=PatientId.generate(),
            corporate_id=corporate_id,
            names=names,
            patient_number=patient_number,
            birth_date=birth_date,
        )

    def change_names(self, names: PersonNames) -> Self:
        """患者氏名を変更する。"""
        return replace(self, names=names)

    def change_birth_date(self, birth_date: PatientBirthDate | None) -> Self:
        """患者の生年月日を変更する。Noneの場合は登録済みの生年月日を解除する。"""
        return replace(self, birth_date=birth_date)
