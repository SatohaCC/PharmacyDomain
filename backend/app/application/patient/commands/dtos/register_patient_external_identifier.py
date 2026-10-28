"""Applicationのregister_patient_external_identifierを定義する。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.patient.entities import PatientExternalIdentifier


@dataclass(frozen=True, kw_only=True)
class PatientExternalIdentifierDto:
    """外部患者ID対応付けの出力データ（DTO）。"""

    id: str
    corporate_id: str
    patient_id: str
    system_name: str
    external_patient_id: str
    store_id: str | None
    is_active: bool

    @classmethod
    def from_entity(
        cls, identifier: PatientExternalIdentifier
    ) -> PatientExternalIdentifierDto:
        """外部患者ID対応付けからDTOを生成する。"""
        return cls(
            id=str(identifier.id.value),
            corporate_id=str(identifier.corporate_id.value),
            patient_id=str(identifier.patient_id.value),
            system_name=identifier.system_name.value,
            external_patient_id=identifier.external_patient_id.value,
            store_id=str(identifier.store_id.value)
            if identifier.store_id is not None
            else None,
            is_active=identifier.is_active,
        )
