"""患者のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

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


class PatientRepository(Protocol):
    """患者集約を永続化・再構築するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> Patient | None:
        """指定された法人内の患者を取得する。

        指定された法人に患者が存在しない場合や、患者が別法人に所属している
        場合は、データの存在を隠すため ``None`` を返す。
        """
        ...

    async def save(self, patient: Patient) -> None:
        """患者を新規登録または変更保存する。"""
        ...

    async def allocate_patient_number(
        self,
        corporate_id: CorporateId,
    ) -> PatientNumber:
        """指定法人で再利用しない患者番号を原子的に採番する。"""
        ...


class PatientExternalIdentifierRepository(Protocol):
    """患者外部識別子を永続化・検索するための操作インターフェース。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        identifier_id: PatientExternalIdentifierId,
    ) -> PatientExternalIdentifier | None:
        """指定法人の外部識別子を取得する。"""
        ...

    async def get_by_source(
        self,
        *,
        corporate_id: CorporateId,
        system_name: ExternalSystemName,
        external_patient_id: ExternalPatientId,
    ) -> PatientExternalIdentifier | None:
        """連携先と外部患者IDの組で対応付けを取得する。"""
        ...

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[PatientExternalIdentifier]:
        """指定法人・患者の外部識別子一覧を取得する。"""
        ...

    async def save(self, identifier: PatientExternalIdentifier) -> None:
        """外部識別子を新規登録または変更保存する。"""
        ...
