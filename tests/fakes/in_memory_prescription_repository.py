"""処方箋Repositoryのインメモリ実装。"""

from __future__ import annotations

import copy

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import (
    PrescriptionDocumentNumber,
    PrescriptionId,
)
from app.domain.prescription.repository import PrescriptionRepository
from app.domain.prescription.services import (
    PrescriptionDocumentNumberUniquenessService,
)


class InMemoryPrescriptionRepository(PrescriptionRepository):
    """法人境界を適用するテスト用処方箋Repository。"""

    def __init__(self) -> None:
        self.items: dict[PrescriptionId, Prescription] = {}

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription | None:
        """指定法人の処方箋だけを取得する。"""
        item = self.items.get(prescription_id)
        if item is None or item.corporate_id != corporate_id:
            return None
        return copy.deepcopy(item)

    async def get_by_document_number(
        self,
        *,
        corporate_id: CorporateId,
        document_number: PrescriptionDocumentNumber,
    ) -> Prescription | None:
        """引換番号や処方箋番号から取得する。"""
        for item in self.items.values():
            if (
                item.corporate_id == corporate_id
                and item.document_number == document_number
            ):
                return copy.deepcopy(item)
        return None

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[Prescription]:
        """指定法人・患者の処方箋だけを一覧する。"""
        return [
            copy.deepcopy(item)
            for item in self.items.values()
            if item.corporate_id == corporate_id and item.patient_id == patient_id
        ]

    async def save(self, prescription: Prescription) -> None:
        """引換番号の重複を原子的に拒否して処方箋を保存する。

        Applicationの事前readは早期エラー用であり原子性の代替ではないため、
        Repository契約として保存の直前にも同じ判定を行う。判定は
        ``PrescriptionDocumentNumberUniquenessService`` を呼び、
        規則の実装が2箇所に分かれないようにする。
        """
        PrescriptionDocumentNumberUniquenessService().ensure_no_conflict(
            prescription,
            [item for item in self.items.values() if item.id != prescription.id],
        )
        self.items[prescription.id] = copy.deepcopy(prescription)
