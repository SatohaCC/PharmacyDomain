"""共通のUnit of Workを各コンテキストのPostgreSQL Repositoryへ配る束。"""

from dataclasses import dataclass
from typing import Self

from app.infrastructure.care_event.postgres.care_event import PostgresEventRepository
from app.infrastructure.care_event.postgres.event_definition import (
    PostgresEventDefinitionRepository,
)
from app.infrastructure.corporate.postgres.corporate import (
    PostgresCorporateRepository,
)
from app.infrastructure.coverage.postgres.coverage_selection_record import (
    PostgresCoverageSelectionRecordRepository,
)
from app.infrastructure.coverage.postgres.patient_coverage import (
    PostgresPatientCoverageRepository,
)
from app.infrastructure.dispensing.postgres.dispensing_process import (
    PostgresDispensingProcessRepository,
)
from app.infrastructure.identity.postgres.account_person import (
    PostgresAccountPersonRepository,
)
from app.infrastructure.identity.postgres.corporate_membership import (
    PostgresCorporateMembershipRepository,
)
from app.infrastructure.identity.postgres.staff_person_link import (
    PostgresStaffPersonLinkRepository,
)
from app.infrastructure.identity.postgres.user_account import (
    PostgresUserAccountRepository,
)
from app.infrastructure.identity.postgres.user_invitation import (
    PostgresUserInvitationRepository,
)
from app.infrastructure.medication_history.postgres.medication_history import (
    PostgresMedicationHistoryRepository,
)
from app.infrastructure.medication_history.postgres.medication_history_category_catalog import (
    PostgresMedicationHistoryCategoryCatalogRepository,
)
from app.infrastructure.medication_history.postgres.patient_medical_profile import (
    PostgresPatientMedicalProfileRepository,
)
from app.infrastructure.medicine_catalog.postgres.medicine_catalog import (
    PostgresMedicineCatalogRepository,
)
from app.infrastructure.patient.postgres.patient import PostgresPatientRepository
from app.infrastructure.patient.postgres.patient_external_identifier import (
    PostgresPatientExternalIdentifierRepository,
)
from app.infrastructure.postgres.connection import PostgresUnitOfWork
from app.infrastructure.prescription.postgres.prescription import (
    PostgresPrescriptionRepository,
)
from app.infrastructure.reception.postgres.reception import (
    PostgresReceptionRepository,
)
from app.infrastructure.staff.postgres.staff import PostgresStaffRepository
from app.infrastructure.store.postgres.store import PostgresStoreRepository
from app.infrastructure.store.postgres.store_manager_assignment import (
    PostgresStoreManagerAssignmentRepository,
)


@dataclass(frozen=True, slots=True)
class PostgresRepositorySet:
    """同じ Unit of Work を共有する Repository の集合。

    全Repositoryが**同一のUoWインスタンス**を持つことが要点である。読み込んだ
    行の世代はUoWが持つので、別々のUoWから作ると同じ行の世代が分裂し、
    楽観ロックが当たらなくなる。
    """

    corporate: PostgresCorporateRepository
    manager_assignment: PostgresStoreManagerAssignmentRepository
    account_person: PostgresAccountPersonRepository
    user_account: PostgresUserAccountRepository
    membership: PostgresCorporateMembershipRepository
    staff_person_link: PostgresStaffPersonLinkRepository
    invitation: PostgresUserInvitationRepository
    store: PostgresStoreRepository
    staff: PostgresStaffRepository
    patient: PostgresPatientRepository
    patient_external_identifier: PostgresPatientExternalIdentifierRepository
    patient_coverage: PostgresPatientCoverageRepository
    coverage_selection_record: PostgresCoverageSelectionRecordRepository
    prescription: PostgresPrescriptionRepository
    dispensing: PostgresDispensingProcessRepository
    event: PostgresEventRepository
    event_definition: PostgresEventDefinitionRepository
    medication_history: PostgresMedicationHistoryRepository
    medication_history_category_catalog: (
        PostgresMedicationHistoryCategoryCatalogRepository
    )
    patient_medical_profile: PostgresPatientMedicalProfileRepository
    medicine_catalog: PostgresMedicineCatalogRepository
    reception: PostgresReceptionRepository

    @classmethod
    def create(cls, unit_of_work: PostgresUnitOfWork) -> Self:
        """1つの Unit of Work から全Repositoryを組み立てる。"""
        return cls(
            manager_assignment=PostgresStoreManagerAssignmentRepository(unit_of_work),
            account_person=PostgresAccountPersonRepository(unit_of_work),
            user_account=PostgresUserAccountRepository(unit_of_work),
            membership=PostgresCorporateMembershipRepository(unit_of_work),
            staff_person_link=PostgresStaffPersonLinkRepository(unit_of_work),
            invitation=PostgresUserInvitationRepository(unit_of_work),
            corporate=PostgresCorporateRepository(unit_of_work),
            store=PostgresStoreRepository(unit_of_work),
            staff=PostgresStaffRepository(unit_of_work),
            patient=PostgresPatientRepository(unit_of_work),
            patient_external_identifier=PostgresPatientExternalIdentifierRepository(
                unit_of_work
            ),
            patient_coverage=PostgresPatientCoverageRepository(unit_of_work),
            coverage_selection_record=PostgresCoverageSelectionRecordRepository(
                unit_of_work
            ),
            prescription=PostgresPrescriptionRepository(unit_of_work),
            dispensing=PostgresDispensingProcessRepository(unit_of_work),
            event=PostgresEventRepository(unit_of_work),
            event_definition=PostgresEventDefinitionRepository(unit_of_work),
            medication_history=PostgresMedicationHistoryRepository(unit_of_work),
            medication_history_category_catalog=(
                PostgresMedicationHistoryCategoryCatalogRepository(unit_of_work)
            ),
            patient_medical_profile=PostgresPatientMedicalProfileRepository(
                unit_of_work
            ),
            medicine_catalog=PostgresMedicineCatalogRepository(unit_of_work),
            reception=PostgresReceptionRepository(unit_of_work),
        )
