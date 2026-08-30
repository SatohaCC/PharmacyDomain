"""受付コンテキストのユースケース束。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.common.clock import Clock
from app.application.composition.coverage_selection_adapter import (
    CoverageSelectionAdapter,
)
from app.application.composition.reception_references import (
    ReceptionPatientReferenceAdapter,
    ReceptionStoreReferenceAdapter,
)
from app.application.corporate.corporate_access import CorporateAccessService
from app.application.reception.get_last_coverage_selection import (
    GetLastCoverageSelectionUseCase,
)
from app.application.reception.record_coverage_selection import (
    RecordCoverageSelectionUseCase,
)
from app.domain.coverage.combination import CoverageSelectionService
from app.infrastructure.composition.repositories import PostgresRepositorySet


@dataclass(frozen=True, slots=True)
class ReceptionUseCases:
    """受付コンテキストのユースケース。"""

    record_coverage_selection: RecordCoverageSelectionUseCase
    get_last_coverage_selection: GetLastCoverageSelectionUseCase


def build_reception_use_cases(
    repositories: PostgresRepositorySet,
    corporate_access: CorporateAccessService,
    clock: Clock,
) -> ReceptionUseCases:
    """受付ユースケースを組み立てる。

    資格の構築（登録時）と再検証（参照時）は同一のアダプタが担う。**同じ規則で
    組み立て直せること**が履歴の真正性の定義なので、別実装に分けると、記録した
    ときの規則と検証するときの規則が食い違いうる。
    """
    repository = repositories.coverage_selection_record
    store_reference = ReceptionStoreReferenceAdapter(repositories.store)
    patient_reference = ReceptionPatientReferenceAdapter(repositories.patient)
    coverage_selection = CoverageSelectionAdapter(
        repositories.patient_coverage, CoverageSelectionService()
    )
    return ReceptionUseCases(
        record_coverage_selection=RecordCoverageSelectionUseCase(
            repository,
            corporate_access,
            store_reference,
            patient_reference,
            coverage_selection,
            clock,
        ),
        get_last_coverage_selection=GetLastCoverageSelectionUseCase(
            repository,
            corporate_access,
            store_reference,
            patient_reference,
            coverage_selection,
        ),
    )
