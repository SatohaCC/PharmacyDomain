"""調剤コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.composition.dispensing_references import (
    DispensingStaffQualificationAdapter,
    DispensingStoreReferenceAdapter,
    PrescriptionSourceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.dispensing.complete_dispensing import CompleteDispensingUseCase
from app.application.dispensing.get_dispensing import GetDispensingUseCase
from app.application.dispensing.list_dispensings_by_prescription import (
    ListDispensingsByPrescriptionUseCase,
)
from app.application.dispensing.record_audit import RecordAuditUseCase
from app.application.dispensing.record_dispensed_content import (
    RecordDispensedContentUseCase,
)
from app.application.dispensing.start_dispensing import StartDispensingUseCase
from app.application.dispensing.verify_dispensing import VerifyDispensingUseCase
from app.domain.dispensing.services import (
    DispensingConsistencyService,
    DispensingIterationUniquenessService,
    DispensingPharmacistService,
)
from app.infrastructure.composition.repositories import PostgresRepositorySet
from app.infrastructure.postgres.unit_of_work import PostgresUnitOfWork


@dataclass(frozen=True, slots=True)
class DispensingUseCases:
    """調剤コンテキストのユースケース。"""

    start: StartDispensingUseCase
    record_dispensed_content: RecordDispensedContentUseCase
    verify: VerifyDispensingUseCase
    record_audit: RecordAuditUseCase
    complete: CompleteDispensingUseCase
    get: GetDispensingUseCase
    list_by_prescription: ListDispensingsByPrescriptionUseCase


def build_dispensing_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
    unit_of_work: PostgresUnitOfWork,
) -> DispensingUseCases:
    """調剤ユースケースを組み立てる。

    処方箋の参照と調剤済への遷移は**同じアダプタ・同じRepositoryインスタンス**が
    担う。読みと書きで別のRepositoryを渡すと、Unit of Work が覚えている世代と
    書き込みが噛み合わなくなる。
    """
    repository = repositories.dispensing
    prescription_source = PrescriptionSourceAdapter(repositories.prescription)
    staff_qualification = DispensingStaffQualificationAdapter(repositories.staff)
    consistency = DispensingConsistencyService()
    pharmacist = DispensingPharmacistService()
    return DispensingUseCases(
        start=StartDispensingUseCase(
            repository,
            corporate_access,
            DispensingStoreReferenceAdapter(repositories.store),
            prescription_source,
            staff_qualification,
            consistency,
            pharmacist,
            DispensingIterationUniquenessService(),
            clock,
        ),
        record_dispensed_content=RecordDispensedContentUseCase(
            repository, corporate_access, prescription_source, consistency
        ),
        verify=VerifyDispensingUseCase(
            repository, corporate_access, staff_qualification, pharmacist, clock
        ),
        record_audit=RecordAuditUseCase(
            repository, corporate_access, staff_qualification, pharmacist, clock
        ),
        complete=CompleteDispensingUseCase(
            repository,
            corporate_access,
            prescription_source,
            unit_of_work,
        ),
        get=GetDispensingUseCase(repository, corporate_access),
        list_by_prescription=ListDispensingsByPrescriptionUseCase(
            repository, corporate_access
        ),
    )
