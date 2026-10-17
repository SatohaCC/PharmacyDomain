"""業務上の失敗を外部技術に依存しない分類へ変換する。"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from enum import StrEnum
from functools import wraps
from typing import Final

from app.application.common.exceptions import (
    ApplicationError,
    AuthorizationError,
    NotFoundError,
)
from app.application.coverage.exceptions import (
    CoveragePatientNotFoundError,
    CoverageStoreNotFoundError,
    PatientCoverageNotFoundError,
)
from app.application.dispensing.exceptions import (
    DispensingNotFoundError,
    DispensingPrescriptionNotFoundError,
    DispensingStaffNotFoundError,
    DispensingStoreNotFoundError,
)
from app.application.identity.resolve_actor import UnavailableIdentityError
from app.application.integration.nsips.exceptions import (
    NsipsPatientIdentityConflictError,
)
from app.application.medication_history.exceptions import (
    MedicationHistoryDispensingNotFoundError,
    MedicationHistoryNotFoundError,
    MedicationHistoryPatientNotFoundError,
    MedicationHistoryPrescriptionNotFoundError,
    MedicationHistoryStaffNotFoundError,
    MedicationHistoryStoreNotFoundError,
    PatientMedicalProfileNotFoundError,
)
from app.application.medicine_catalog.exceptions import MedicineNotFoundError
from app.application.patient.exceptions import (
    PatientExternalIdentifierNotFoundError,
    PatientNotFoundError,
    PatientStoreNotFoundError,
)
from app.application.prescription.exceptions import (
    PrescriptionCoverageSelectionNotFoundError,
    PrescriptionNotFoundError,
    PrescriptionPatientNotFoundError,
    PrescriptionPharmacistNotFoundError,
    PrescriptionStoreNotFoundError,
)
from app.application.staff.exceptions import (
    StaffNotFoundError as StaffApplicationNotFoundError,
)
from app.application.store.exceptions import StoreNotFoundError
from app.domain.care_event.exceptions import (
    EventAlreadyAssociatedError,
    EventDefinitionAlreadyExistsError,
)
from app.domain.corporate.exceptions import CorporateNameAlreadyExistsError
from app.domain.coverage.exceptions import (
    CoverageDeactivationAlreadyFixedError,
    CoveragePeriodConflictError,
)
from app.domain.dispensing.exceptions import DispensingAlreadyExistsError
from app.domain.foundation.exceptions import ConcurrentModificationError, DomainError
from app.domain.identity.exceptions import IdentityConflictError
from app.domain.medication_history.exceptions import (
    AdverseReactionNotFoundError,
    AllergyNotFoundError,
    ConcurrentMedicationNotFoundError,
    FollowUpNotFoundError,
    MajorCategoryNotFoundError,
    MedicalConditionNotFoundError,
    MedicationHistoryAlreadyExistsError,
    MedicationHistoryAlreadyFinalizedError,
    PatientMedicalProfileAlreadyExistsError,
    TracingReportAlreadyRespondedError,
    TracingReportNotFoundError,
)
from app.domain.medicine_catalog.exceptions import MedicineEffectivePeriodConflictError
from app.domain.patient.exceptions import (
    PatientExternalIdentifierAlreadyExistsError,
    PatientHeadingConflictError,
    PatientStateConflictError,
)
from app.domain.prescription.exceptions import (
    InquiryAlreadyResolvedError,
    InquiryNotFoundError,
    PrescriptionDocumentNumberAlreadyExistsError,
)
from app.domain.reception.exceptions import ReceptionEventAlreadyAssociatedError
from app.domain.shared.preservation import PreservationPolicyNotFoundError
from app.domain.staff.exceptions import (
    AffiliationDateConflictError,
    ClosedStoreAssignmentError,
    ConcurrentStoreConflictError,
    StaffCodeAlreadyExistsError,
)
from app.domain.staff.exceptions import StaffNotFoundError as StaffDomainNotFoundError
from app.domain.store.exceptions import (
    InsurancePharmacyNumberAlreadyExistsError,
    StoreCodeAlreadyExistsError,
    StoreNameAlreadyExistsError,
)
from app.domain.store.lifecycle import StoreStateConflictError
from app.domain.store.manager_assignment import (
    ManagerAbsenceConflictError,
    ManagerAssignmentStateConflictError,
)
from app.domain.store.manager_repository import (
    ManagerAssignmentConflictError,
    ManagerExclusiveDutyConflictError,
)


class FailureKind(StrEnum):
    """HTTP等の配送形式から独立した失敗分類。"""

    INVALID_STATE = "invalid_state"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


class ApplicationFailure(ApplicationError):
    """外部境界へ公開できる業務失敗。元例外型は公開契約に含めない。"""

    def __init__(self, message: str, *, code: str, kind: FailureKind) -> None:
        super().__init__(message, code=code)
        self.kind = kind


_KIND_BY_EXCEPTION: Final[Mapping[type[BaseException], FailureKind]] = {
    # --- 基底: 個別に載っていないものはここへ落ちる ---
    # 「形式は正しいが業務ルール上そのままでは処理できない」が既定の意味。
    DomainError: FailureKind.INVALID_STATE,
    ApplicationError: FailureKind.INVALID_STATE,
    # --- 401: 主体がまだ決まっていない ---
    UnavailableIdentityError: FailureKind.UNAUTHENTICATED,
    IdentityConflictError: FailureKind.CONFLICT,
    NsipsPatientIdentityConflictError: FailureKind.CONFLICT,
    ManagerAbsenceConflictError: FailureKind.CONFLICT,
    ManagerAssignmentConflictError: FailureKind.CONFLICT,
    ManagerExclusiveDutyConflictError: FailureKind.CONFLICT,
    ManagerAssignmentStateConflictError: FailureKind.CONFLICT,
    StoreStateConflictError: FailureKind.CONFLICT,
    ClosedStoreAssignmentError: FailureKind.CONFLICT,
    PatientHeadingConflictError: FailureKind.CONFLICT,
    PatientStateConflictError: FailureKind.CONFLICT,
    # --- 403: 主体は判明したうえでの拒否 ---
    # 別テナントのリソースは TenantBoundaryNotFoundError（404）として隠すので、
    # ここへ来るのは自テナント内の権限不足だけである。
    AuthorizationError: FailureKind.FORBIDDEN,
    # --- 404: 未検出とテナント境界 ---
    # コンテキストごとの *NotFoundError は基底がまちまちなので個別に載せる。
    NotFoundError: FailureKind.NOT_FOUND,
    CoveragePatientNotFoundError: FailureKind.NOT_FOUND,
    CoverageStoreNotFoundError: FailureKind.NOT_FOUND,
    PatientCoverageNotFoundError: FailureKind.NOT_FOUND,
    DispensingNotFoundError: FailureKind.NOT_FOUND,
    DispensingPrescriptionNotFoundError: FailureKind.NOT_FOUND,
    DispensingStaffNotFoundError: FailureKind.NOT_FOUND,
    DispensingStoreNotFoundError: FailureKind.NOT_FOUND,
    MedicationHistoryDispensingNotFoundError: FailureKind.NOT_FOUND,
    MedicationHistoryNotFoundError: FailureKind.NOT_FOUND,
    MedicationHistoryPatientNotFoundError: FailureKind.NOT_FOUND,
    MedicationHistoryPrescriptionNotFoundError: FailureKind.NOT_FOUND,
    MedicationHistoryStaffNotFoundError: FailureKind.NOT_FOUND,
    MedicationHistoryStoreNotFoundError: FailureKind.NOT_FOUND,
    PatientMedicalProfileNotFoundError: FailureKind.NOT_FOUND,
    MedicineNotFoundError: FailureKind.NOT_FOUND,
    PatientExternalIdentifierNotFoundError: FailureKind.NOT_FOUND,
    PatientNotFoundError: FailureKind.NOT_FOUND,
    PatientStoreNotFoundError: FailureKind.NOT_FOUND,
    PrescriptionCoverageSelectionNotFoundError: FailureKind.NOT_FOUND,
    PrescriptionNotFoundError: FailureKind.NOT_FOUND,
    PrescriptionPatientNotFoundError: FailureKind.NOT_FOUND,
    PrescriptionPharmacistNotFoundError: FailureKind.NOT_FOUND,
    PrescriptionStoreNotFoundError: FailureKind.NOT_FOUND,
    StaffApplicationNotFoundError: FailureKind.NOT_FOUND,
    StoreNotFoundError: FailureKind.NOT_FOUND,
    ConcurrentMedicationNotFoundError: FailureKind.NOT_FOUND,
    AllergyNotFoundError: FailureKind.NOT_FOUND,
    AdverseReactionNotFoundError: FailureKind.NOT_FOUND,
    MedicalConditionNotFoundError: FailureKind.NOT_FOUND,
    InquiryNotFoundError: FailureKind.NOT_FOUND,
    StaffDomainNotFoundError: FailureKind.NOT_FOUND,
    MajorCategoryNotFoundError: FailureKind.NOT_FOUND,
    FollowUpNotFoundError: FailureKind.NOT_FOUND,
    TracingReportNotFoundError: FailureKind.NOT_FOUND,
    PreservationPolicyNotFoundError: FailureKind.NOT_FOUND,
    # --- 409: 既存のデータ・状態と衝突する ---
    ConcurrentModificationError: FailureKind.CONFLICT,
    CorporateNameAlreadyExistsError: FailureKind.CONFLICT,
    CoverageDeactivationAlreadyFixedError: FailureKind.CONFLICT,
    CoveragePeriodConflictError: FailureKind.CONFLICT,
    DispensingAlreadyExistsError: FailureKind.CONFLICT,
    EventAlreadyAssociatedError: FailureKind.CONFLICT,
    EventDefinitionAlreadyExistsError: FailureKind.CONFLICT,
    MedicationHistoryAlreadyExistsError: FailureKind.CONFLICT,
    MedicationHistoryAlreadyFinalizedError: FailureKind.CONFLICT,
    PatientMedicalProfileAlreadyExistsError: FailureKind.CONFLICT,
    TracingReportAlreadyRespondedError: FailureKind.CONFLICT,
    MedicineEffectivePeriodConflictError: FailureKind.CONFLICT,
    PatientExternalIdentifierAlreadyExistsError: FailureKind.CONFLICT,
    InquiryAlreadyResolvedError: FailureKind.CONFLICT,
    PrescriptionDocumentNumberAlreadyExistsError: FailureKind.CONFLICT,
    AffiliationDateConflictError: FailureKind.CONFLICT,
    ReceptionEventAlreadyAssociatedError: FailureKind.CONFLICT,
    ConcurrentStoreConflictError: FailureKind.CONFLICT,
    StaffCodeAlreadyExistsError: FailureKind.CONFLICT,
    InsurancePharmacyNumberAlreadyExistsError: FailureKind.CONFLICT,
    StoreCodeAlreadyExistsError: FailureKind.CONFLICT,
    StoreNameAlreadyExistsError: FailureKind.CONFLICT,
}


def kind_for_type(error_type: type[BaseException]) -> FailureKind:
    """生成に引数が必要な例外も継承順で分類する。"""
    for klass in error_type.__mro__:
        kind = _KIND_BY_EXCEPTION.get(klass)
        if kind is not None:
            return kind
    raise LookupError(f"{error_type.__name__}は業務失敗の分類対象ではありません。")


def describe_failure(error: Exception) -> ApplicationFailure:
    """公開コード・メッセージを維持し、未知の失敗を業務失敗にしない。"""
    if isinstance(error, ApplicationFailure):
        return error
    if not isinstance(error, (DomainError, ApplicationError)):
        raise error
    return ApplicationFailure(
        error.message, code=error.code, kind=kind_for_type(type(error))
    )


def translate_errors[**P, R](
    operation: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """外側の実行境界でDomain例外をApplicationの失敗へ変換する。"""

    @wraps(operation)
    async def execute(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await operation(*args, **kwargs)
        except DomainError as error:
            raise describe_failure(error) from error

    return execute


@asynccontextmanager
async def execution_scope[T](scope: AbstractAsyncContextManager[T]) -> AsyncIterator[T]:
    """確定時のDomain例外も公開境界で変換し、破棄処理は元のUoWへ伝える。"""
    try:
        async with scope as value:
            yield value
    except DomainError as error:
        raise describe_failure(error) from error
