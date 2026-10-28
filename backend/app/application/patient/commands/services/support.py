"""Applicationのsupportを定義する。"""

from __future__ import annotations

from app.application.patient.errors import PatientNotFoundError
from app.domain.corporate.identifiers import CorporateId
from app.domain.patient.entities import Patient
from app.domain.patient.identifiers import PatientId
from app.domain.patient.repositories import PatientRepository


async def load_patient_or_raise(
    repository: PatientRepository, *, corporate_id: CorporateId, patient_id: PatientId
) -> Patient:
    """指定法人の患者を取得し、存在しない場合は404相当の例外を送出する。"""
    patient = await repository.get(corporate_id=corporate_id, patient_id=patient_id)
    if patient is None:
        raise PatientNotFoundError(
            f"指定された患者（ID: {patient_id.value}）が見つかりません。"
        )
    return patient
