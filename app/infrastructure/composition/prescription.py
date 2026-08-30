"""処方箋コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.composition.medicine_restriction_adapter import (
    MedicineCatalogRestrictionAdapter,
)
from app.application.composition.prescription_references import (
    CoverageSelectionPublicExpenseAdapter,
    PrescriptionPatientReferenceAdapter,
    PrescriptionStaffQualificationAdapter,
    PrescriptionStoreReferenceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.prescription.cancel_prescription import CancelPrescriptionUseCase
from app.application.prescription.get_prescription import GetPrescriptionUseCase
from app.application.prescription.ready_for_dispensing import ReadyForDispensingUseCase
from app.application.prescription.register_prescription import (
    RegisterPrescriptionUseCase,
)
from app.application.prescription.resolve_inquiry import ResolveInquiryUseCase
from app.application.prescription.start_inquiry import StartInquiryUseCase
from app.domain.prescription.services import (
    InquiryPharmacistService,
    NarcoticPrescriptionService,
    PrescriptionDocumentNumberUniquenessService,
    PublicExpenseBurdenService,
    RefillEligibilityService,
)
from app.infrastructure.composition.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class PrescriptionUseCases:
    """処方箋コンテキストのユースケース。"""

    register: RegisterPrescriptionUseCase
    get: GetPrescriptionUseCase
    ready_for_dispensing: ReadyForDispensingUseCase
    cancel: CancelPrescriptionUseCase
    start_inquiry: StartInquiryUseCase
    resolve_inquiry: ResolveInquiryUseCase


def build_prescription_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> PrescriptionUseCases:
    """処方箋ユースケースを組み立てる。"""
    repository = repositories.prescription
    return PrescriptionUseCases(
        register=RegisterPrescriptionUseCase(
            repository,
            corporate_access,
            PrescriptionStoreReferenceAdapter(repositories.store),
            PrescriptionPatientReferenceAdapter(repositories.patient),
            MedicineCatalogRestrictionAdapter(repositories.medicine_catalog),
            CoverageSelectionPublicExpenseAdapter(
                repositories.coverage_selection_record
            ),
            PrescriptionDocumentNumberUniquenessService(),
            NarcoticPrescriptionService(),
            RefillEligibilityService(),
            PublicExpenseBurdenService(),
        ),
        get=GetPrescriptionUseCase(repository, corporate_access),
        ready_for_dispensing=ReadyForDispensingUseCase(repository, corporate_access),
        cancel=CancelPrescriptionUseCase(repository, corporate_access),
        start_inquiry=StartInquiryUseCase(
            repository,
            corporate_access,
            PrescriptionStaffQualificationAdapter(repositories.staff),
            InquiryPharmacistService(),
            clock,
        ),
        resolve_inquiry=ResolveInquiryUseCase(repository, corporate_access, clock),
    )
