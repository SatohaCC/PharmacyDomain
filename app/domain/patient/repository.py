"""患者のリポジトリインターフェース。"""

from __future__ import annotations

from typing import Protocol

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import PatientId


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
