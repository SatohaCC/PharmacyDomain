"""患者と外部システムの識別子を結び付ける集約。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Self

from app.base.domain.entity import AggregateRoot
from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientExternalIdentifierId,
    PatientId,
)


@dataclass(frozen=True, eq=False, kw_only=True)
class PatientExternalIdentifier(AggregateRoot[PatientExternalIdentifierId]):
    """連携先ごとの外部患者IDを管理する集約ルート。"""

    id: PatientExternalIdentifierId
    corporate_id: CorporateId
    patient_id: PatientId
    system_name: ExternalSystemName
    external_patient_id: ExternalPatientId
    is_active: bool = True

    @classmethod
    def create(
        cls,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
        system_name: ExternalSystemName,
        external_patient_id: ExternalPatientId,
    ) -> Self:
        """外部患者IDの対応付けを生成する。"""
        return cls(
            id=PatientExternalIdentifierId.generate(),
            corporate_id=corporate_id,
            patient_id=patient_id,
            system_name=system_name,
            external_patient_id=external_patient_id,
        )

    def deactivate(self) -> Self:
        """外部IDの対応付けを無効化する。"""
        return replace(self, is_active=False)
