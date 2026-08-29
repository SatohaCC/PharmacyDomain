"""処方箋の PostgreSQL Repository。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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
from app.infrastructure.postgres.codec import (
    PersistenceMappingError,
    decode_aggregate,
    encode_aggregate,
)
from app.infrastructure.postgres.constraints import constraint_name
from app.infrastructure.postgres.repository_base import PostgresRepositoryBase
from app.infrastructure.postgres.schema import prescriptions


def row_values(prescription: Prescription) -> dict[str, object]:
    """集約から、payload と検索・一意性用の列を組み立てる。"""
    return {
        "id": prescription.id.value,
        "corporate_id": prescription.corporate_id.value,
        "store_id": prescription.store_id.value,
        "patient_id": prescription.patient_id.value,
        "source_type": prescription.source_type.value,
        "document_number": prescription.document_number.value,
        "status": prescription.status.value,
        "payload": encode_aggregate(prescription),
    }


class PostgresPrescriptionRepository(PostgresRepositoryBase, PrescriptionRepository):
    """処方箋集約を PostgreSQL へ保存・検索する。"""

    async def get(
        self,
        *,
        corporate_id: CorporateId,
        prescription_id: PrescriptionId,
    ) -> Prescription | None:
        """法人境界を含めてIDで処方箋を検索する。"""
        result = await self.session.execute(
            select(prescriptions).where(
                prescriptions.c.corporate_id == corporate_id.value,
                prescriptions.c.id == prescription_id.value,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=prescriptions.name,
            )
        )

    async def get_by_document_number(
        self,
        *,
        corporate_id: CorporateId,
        document_number: PrescriptionDocumentNumber,
    ) -> Prescription | None:
        """法人内の処方箋番号から処方箋を検索する。"""
        result = await self.session.execute(
            select(prescriptions)
            .where(
                prescriptions.c.corporate_id == corporate_id.value,
                prescriptions.c.document_number == document_number.value,
            )
            .order_by(prescriptions.c.id)
            .limit(1)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _decode_row(
            self.remember_version(
                cast(Mapping[str, object], row),
                namespace=prescriptions.name,
            )
        )

    async def list_by_patient(
        self,
        *,
        corporate_id: CorporateId,
        patient_id: PatientId,
    ) -> list[Prescription]:
        """法人・患者で処方箋をID順に列挙する。"""
        result = await self.session.execute(
            select(prescriptions)
            .where(
                prescriptions.c.corporate_id == corporate_id.value,
                prescriptions.c.patient_id == patient_id.value,
            )
            .order_by(prescriptions.c.id)
        )
        return [
            _decode_row(
                self.remember_version(
                    cast(Mapping[str, object], row),
                    namespace=prescriptions.name,
                )
            )
            for row in result.mappings().all()
        ]

    async def save(self, prescription: Prescription) -> None:
        """処方箋を保存し、電子処方箋番号の重複を原子的に拒否する。"""
        try:
            await self.upsert(
                prescriptions,
                aggregate_id=prescription.id.value,
                values=row_values(prescription),
            )
        except IntegrityError as error:
            if constraint_name(error) == "uq_prescriptions_electronic_document_number":
                raise PrescriptionDocumentNumberAlreadyExistsError(
                    document_number=prescription.document_number.value
                ) from error
            raise


def _decode_row(row: Mapping[str, object]) -> Prescription:
    """DB行の検索列と payload の整合性を確認して復元する。"""
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise PersistenceMappingError(
            "処方箋の payload が JSON オブジェクトではありません。"
        )
    prescription = decode_aggregate(payload, Prescription)
    if (
        prescription.id.value != row.get("id")
        or prescription.corporate_id.value != row.get("corporate_id")
        or prescription.store_id.value != row.get("store_id")
        or prescription.patient_id.value != row.get("patient_id")
        or prescription.source_type.value != row.get("source_type")
        or prescription.document_number.value != row.get("document_number")
        or prescription.status.value != row.get("status")
    ):
        raise PersistenceMappingError("処方箋の検索列と payload が一致しません。")
    return prescription
