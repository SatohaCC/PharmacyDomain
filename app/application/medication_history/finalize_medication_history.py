"""薬歴を確定し、頭書きへ投影するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import Clock
from app.application.common.exceptions import AuthorizationError
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.reference import (
    StaffQualificationBoundary,
)
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.patient_medical_profile import PatientMedicalProfile
from app.domain.medication_history.primitives import (
    CounselingTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.repository import (
    MedicationHistoryCategoryCatalogRepository,
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class FinalizeMedicationHistoryCommand:
    """薬歴確定の入力データ。"""

    corporate_id: str
    record_id: str
    counseled_at: datetime | None = None
    finalized_by: str | None = None
    finalized_at: datetime | None = None
    delay_reason: str | None = None


class FinalizeMedicationHistoryUseCase:
    """薬歴を確定し、頭書きへ差分を投影する。

    **保存順序は ``save(record)`` → ``save(profile)`` で固定する。**
    前者が成功して後者が失敗した場合、頭書きは薬歴から再構築して回復できる
    （``RebuildPatientMedicalProfileUseCase``）。逆順にすると、根拠のない
    頭書きレコードだけが残り、どの薬歴に由来するかを追えなくなる。

    2つの書き込みを同じトランザクションへ入れる開始・確定は実行スコープが
    担い、ユースケースは必須の UnitOfWork で境界の開始済みだけを確認する。
    PostgreSQL 経路では後者が失敗すれば薬歴の確定ごと巻き戻る。トランザクションを
    持たない経路（インメモリ）では、何もしない UnitOfWork を渡しても頭書きだけが
    取り残されうるが、**頭書きを投影と定義しているので薬歴から再構築して回復
    できる**（``RebuildPatientMedicalProfileUseCase``）。
    """

    def __init__(
        self,
        record_repository: MedicationHistoryRepository,
        profile_repository: PatientMedicalProfileRepository,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
        category_catalog_repository: MedicationHistoryCategoryCatalogRepository
        | None = None,
        staff_qualification: StaffQualificationBoundary | None = None,
        counselor_service: CounselorQualificationService | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._category_catalog_repository = category_catalog_repository
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._clock = clock

    async def execute(
        self, command: FinalizeMedicationHistoryCommand
    ) -> MedicationHistoryDto:
        """SOAPの充足と確定者の資格を確認して確定し、頭書きへ投影する。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        record = await load_record_or_raise(
            self._record_repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(command.record_id),
        )
        counselor_id = record.counselor_id
        counseled_at = record.counseled_at
        qualified_staff_ids: set[StaffId] = set()
        if counselor_id is None or counseled_at is None:
            if command.counseled_at is None:
                raise MedicationHistoryDomainError(
                    "取込下書きを確定するには実際の指導日時が必要です。"
                )
            actor = self._corporate_access.actor
            if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
                raise AuthorizationError(
                    "取込下書きの確定にはスタッフを特定できるActorが必要です。"
                )
            counselor_id = actor.staff_id
            counseled_at = CounselingTimestamp(command.counseled_at)
            if (
                self._staff_qualification is not None
                and self._counselor_service is not None
            ):
                qualifications = await self._staff_qualification.get_qualifications(
                    corporate_id=corporate_id, staff_id=counselor_id
                )
                self._counselor_service.ensure_pharmacist(qualifications)
                qualified_staff_ids.add(counselor_id)
        elif command.counseled_at is not None and (
            CounselingTimestamp(command.counseled_at) != counseled_at
        ):
            raise MedicationHistoryDomainError(
                "記録済みの指導日時は確定時に変更できません。"
            )

        if counselor_id is None or counseled_at is None:
            raise MedicationHistoryDomainError(
                "薬歴を確定するには実際の指導者と指導日時が必要です。"
            )
        finalized_by = (
            StaffId.parse(command.finalized_by)
            if command.finalized_by is not None
            else record.counselor_id or counselor_id
        )
        if (
            self._staff_qualification is not None
            and self._counselor_service is not None
            and finalized_by not in qualified_staff_ids
        ):
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id, staff_id=finalized_by
            )
            self._counselor_service.ensure_pharmacist(qualifications)

        if command.finalized_at is not None:
            finalized_at = FinalizedTimestamp(command.finalized_at)
        elif self._clock is not None:
            finalized_at = FinalizedTimestamp(self._clock.now())
        else:
            finalized_at = FinalizedTimestamp(counseled_at.value)

        delay_reason = (
            FinalizationDelayReason(command.delay_reason)
            if command.delay_reason is not None
            else None
        )

        if self._category_catalog_repository is not None:
            catalog = await self._category_catalog_repository.get(
                corporate_id=corporate_id
            )
            if catalog is not None:
                catalog.validate_record_compliance(record)

        finalized = record.finalize(
            counselor_id=counselor_id,
            counseled_at=counseled_at,
            finalized_at=finalized_at,
            finalized_by=finalized_by,
            delay_reason=delay_reason,
        )
        await self._record_repository.save(finalized)
        await self._project_to_profile(finalized)
        return MedicationHistoryDto.from_entity(finalized)

    async def _project_to_profile(self, record: MedicationHistoryRecord) -> None:
        """確定した薬歴の差分を頭書きへ適用して保存する。

        頭書きが未作成のときは空から作る。Repository の ``None`` は欠損ではなく
        「まだ投影されていない」を意味する。
        """
        profile = await self._profile_repository.get_by_patient(
            corporate_id=record.corporate_id,
            patient_id=record.patient_id,
        )
        if profile is None:
            profile = PatientMedicalProfile.empty_for(
                corporate_id=record.corporate_id,
                patient_id=record.patient_id,
            )
        await self._profile_repository.save(profile.apply(record))
