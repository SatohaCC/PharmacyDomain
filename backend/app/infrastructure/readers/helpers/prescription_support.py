"""Applicationのprescription_supportを定義する。"""

from __future__ import annotations

from app.application.prescription.errors import PrescriptionNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.prescription.entities import Prescription
from app.domain.prescription.identifiers import PrescriptionId
from app.domain.prescription.repositories import PrescriptionRepository


async def load_prescription_or_raise(
    repository: PrescriptionRepository,
    *,
    corporate_id: CorporateId,
    prescription_id: PrescriptionId,
) -> Prescription:
    """指定法人の処方箋を取得し、存在しなければ404相当を送出する。"""
    prescription = await repository.get(
        corporate_id=corporate_id, prescription_id=prescription_id
    )
    if prescription is None:
        raise PrescriptionNotFoundError()
    return prescription
