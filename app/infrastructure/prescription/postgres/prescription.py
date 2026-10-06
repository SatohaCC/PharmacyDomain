"""処方箋集約の PostgreSQL Repository。

電子処方箋番号は法人内で一意だが、紙の処方箋は同じ番号を持ちうる。一意性を
課すのは電子処方箋の行だけなので、最終防衛は部分一意インデックスになる。
"""

from __future__ import annotations

from sqlalchemy import select

from app.domain.corporate.primitives import CorporateId
from app.domain.patient.primitives import PatientId
from app.domain.prescription.exceptions import (
    PrescriptionDocumentNumberAlreadyExistsError,
)
from app.domain.prescription.prescription import Prescription
from app.domain.prescription.primitives import (
    PrescriptionDocumentNumber,
    PrescriptionId,
)
from app.domain.prescription.repository import PrescriptionRepository
from app.infrastructure.postgres.repository_base import (
    AggregateMapping,
    PostgresRepositoryBase,
)
from app.infrastructure.postgres.schema import prescriptions


def _prescription_columns(prescription: Prescription) -> dict[str, object]:
    """検索・一意性制約に使う列を処方箋から導く。"""
    return {
        "id": prescription.id.value,
        "corporate_id": prescription.corporate_id.value,
        "store_id": prescription.store_id.value,
        "patient_id": prescription.patient_id.value,
        "source_type": prescription.source_type.value,
        "document_number": prescription.document_number.value,
        "status": prescription.status.value,
    }


PRESCRIPTION_MAPPING = AggregateMapping(
    table=prescriptions,
    aggregate_type=Prescription,
    label="処方箋",
    search_columns=_prescription_columns,
)


class PostgresPrescriptionRepository(PostgresRepositoryBase, PrescriptionRepository):
    """処方箋集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription | None:
        """法人境界を含めてIDで処方箋を検索する。"""
        return await self.get_by_id(
            PRESCRIPTION_MAPPING, prescription_id, corporate_id=corporate_id
        )

    async def get_by_document_number(
        self,
        *,
        corporate_id: CorporateId,
        document_number: PrescriptionDocumentNumber,
    ) -> Prescription | None:
        """法人内の処方箋番号から処方箋を検索する。"""
        return await self.find_one(
            PRESCRIPTION_MAPPING,
            select(prescriptions)
            .where(
                prescriptions.c.corporate_id == corporate_id.value,
                prescriptions.c.document_number == document_number.value,
            )
            .order_by(prescriptions.c.id)
            .limit(1),
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[Prescription]:
        """法人・患者で処方箋をID順に列挙する。"""
        return await self.find_all(
            PRESCRIPTION_MAPPING,
            select(prescriptions)
            .where(
                prescriptions.c.corporate_id == corporate_id.value,
                prescriptions.c.patient_id == patient_id.value,
            )
            .order_by(prescriptions.c.id),
        )

    async def save(self, prescription: Prescription) -> None:
        """処方箋を保存し、電子処方箋番号の重複を原子的に拒否する。"""
        await self.save_with_conflict_map(
            PRESCRIPTION_MAPPING,
            prescription,
            conflicts={
                "uq_prescriptions_electronic_document_number": lambda: (
                    PrescriptionDocumentNumberAlreadyExistsError(
                        document_number=prescription.document_number.value
                    )
                ),
            },
        )
