"""患者・外部識別子Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientExternalIdentifierId,
    PatientId,
    PatientNumber,
)
from app.domain.patient.repository import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)


class InMemoryPatientRepository(PatientRepository):
    """法人境界を適用するテスト用患者Repository。"""

    def __init__(self) -> None:
        self.items: dict[PatientId, Patient] = {}
        self._sequences: dict[CorporateId, int] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> Patient | None:
        """指定法人の患者だけを取得する。"""
        item = self.items.get(patient_id)
        if item is None or item.corporate_id != corporate_id:
            return None
        return copy.deepcopy(item)

    async def save(self, patient: Patient) -> None:
        """患者をコピーして保存する。"""
        self.items[patient.id] = copy.deepcopy(patient)

    async def allocate_patient_number(
        self,
        corporate_id: CorporateId,
    ) -> PatientNumber:
        """法人ごとに連番の患者番号を採番する。"""
        next_number = self._sequences.get(corporate_id, 0) + 1
        self._sequences[corporate_id] = next_number
        return PatientNumber(next_number)


class InMemoryPatientExternalIdentifierRepository(PatientExternalIdentifierRepository):
    """法人境界を適用するテスト用外部識別子Repository。"""

    def __init__(self) -> None:
        self.items: dict[PatientExternalIdentifierId, PatientExternalIdentifier] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        identifier_id: PatientExternalIdentifierId,
    ) -> PatientExternalIdentifier | None:
        """指定法人の外部識別子だけを取得する。"""
        item = self.items.get(identifier_id)
        if item is None or item.corporate_id != corporate_id:
            return None
        return copy.deepcopy(item)

    async def get_by_source(
        self,
        *,
        corporate_id: CorporateId,
        system_name: ExternalSystemName,
        external_patient_id: ExternalPatientId,
    ) -> PatientExternalIdentifier | None:
        """連携先と外部患者IDの組で対応付けを取得する。

        無効化済みの行も返す。「有効な対応付けだけを一意とみなす」判断は
        ユースケース側の責務であり、Repositoryは保存した行をそのまま返す。
        """
        for item in self.items.values():
            if (
                item.corporate_id == corporate_id
                and item.system_name == system_name
                and item.external_patient_id == external_patient_id
            ):
                return copy.deepcopy(item)
        return None

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientExternalIdentifier]:
        """指定法人・患者の外部識別子一覧を取得する。"""
        return [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.patient_id == patient_id
        ]

    async def save(self, identifier: PatientExternalIdentifier) -> None:
        """外部識別子をコピーして保存する。"""
        self.items[identifier.id] = copy.deepcopy(identifier)
