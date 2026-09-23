"""患者集約のエンティティ・値オブジェクト・リポジトリインターフェース。"""

from app.domain.patient.exceptions import (
    PatientDomainError,
    PatientExternalIdentifierAlreadyExistsError,
    PatientStateConflictError,
)
from app.domain.patient.external_identifier import PatientExternalIdentifier
from app.domain.patient.lifecycle import (
    PatientStatus,
    PatientStatusChange,
    PatientStatusReason,
)
from app.domain.patient.merge_service import PatientMergeService
from app.domain.patient.patient import Patient
from app.domain.patient.primitives import (
    ExternalPatientId,
    ExternalSystemName,
    PatientAddress,
    PatientBirthDate,
    PatientExternalIdentifierId,
    PatientGenderCode,
    PatientId,
    PatientNumber,
    PatientPhoneNumber,
    PatientPostalCode,
)
from app.domain.patient.repository import (
    PatientExternalIdentifierRepository,
    PatientRepository,
)

__all__ = [
    "ExternalPatientId",
    "ExternalSystemName",
    "Patient",
    "PatientAddress",
    "PatientBirthDate",
    "PatientDomainError",
    "PatientExternalIdentifier",
    "PatientExternalIdentifierAlreadyExistsError",
    "PatientExternalIdentifierId",
    "PatientExternalIdentifierRepository",
    "PatientGenderCode",
    "PatientId",
    "PatientMergeService",
    "PatientNumber",
    "PatientPhoneNumber",
    "PatientPostalCode",
    "PatientRepository",
    "PatientStateConflictError",
    "PatientStatus",
    "PatientStatusChange",
    "PatientStatusReason",
]
