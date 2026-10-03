"""薬歴を確定し、頭書きへ投影するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission, ResolvedActorContext
from app.application.common.clock import BUSINESS_TIMEZONE, Clock, business_now
from app.application.common.exceptions import AuthorizationError
from app.application.common.organization_lock import OrganizationLock
from app.application.common.unit_of_work import UnitOfWork
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.profile_projection_service import (
    PatientMedicalProfileProjectionService,
)
from app.application.medication_history.reference import (
    MedicationHistoryEventOccurrenceBoundary,
    StaffQualificationBoundary,
)
from app.application.medication_history.support import load_record_or_raise, parse_enum
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.exceptions import MedicationHistoryDomainError
from app.domain.medication_history.medication_history_record import (
    MedicationHistoryRecord,
)
from app.domain.medication_history.primitives import (
    CounselingTimestamp,
    FinalizationDelayReason,
    FinalizedTimestamp,
    MedicationHistoryRecordId,
    MedicationHistoryReviewResult,
)
from app.domain.medication_history.repository import (
    MedicationHistoryCategoryCatalogRepository,
    MedicationHistoryRepository,
    PatientMedicalProfileRepository,
)
from app.domain.medication_history.services import CounselorQualificationService
from app.domain.shared.preservation import (
    PreservationPolicyCatalog,
    PreservationRecordKind,
)
from app.domain.staff.primitives import StaffId


@dataclass(frozen=True, kw_only=True)
class FinalizeMedicationHistoryCommand:
    """薬歴確定の入力データ。"""

    corporate_id: str
    record_id: str
    counseled_at: datetime | None = None
    event_occurred_at: datetime | None = None
    delay_reason: str | None = None
    review_result: str | None = None


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
        *,
        organization_lock: OrganizationLock,
        category_catalog_repository: MedicationHistoryCategoryCatalogRepository
        | None = None,
        staff_qualification: StaffQualificationBoundary | None = None,
        counselor_service: CounselorQualificationService | None = None,
        clock: Clock | None = None,
        event_occurrence: MedicationHistoryEventOccurrenceBoundary | None = None,
        projection_service: PatientMedicalProfileProjectionService | None = None,
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work
        self._organization_lock = organization_lock
        self._category_catalog_repository = category_catalog_repository
        self._staff_qualification = staff_qualification
        self._counselor_service = counselor_service
        self._clock = clock
        self._event_occurrence = event_occurrence
        self._projection_service = (
            projection_service
            or PatientMedicalProfileProjectionService(
                record_repository=record_repository,
                profile_repository=profile_repository,
            )
        )

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
        await self._organization_lock.acquire(
            f"medication-history-retention:{corporate_id.value}:{record.patient_id.value}"
        )
        # ロック待ちの間に別リクエストが同じ薬歴を確定した可能性があるため、
        # 患者単位ロックを得た後に対象も読み直す。
        record = await load_record_or_raise(
            self._record_repository,
            corporate_id=corporate_id,
            record_id=record.id,
        )
        if command.review_result is None:
            raise MedicationHistoryDomainError(
                "薬歴確定時のレビュー結果を指定してください。"
            )
        review_result = parse_enum(
            MedicationHistoryReviewResult,
            command.review_result,
            "薬歴レビュー結果",
        )

        actor = self._corporate_access.actor
        if not isinstance(actor, ResolvedActorContext) or actor.staff_id is None:
            raise AuthorizationError(
                "薬歴の確認にはスタッフを特定できるActorが必要です。"
            )
        finalizer_id = actor.staff_id
        counselor_id = record.counselor_id
        counseled_at = record.counseled_at
        qualified_staff_ids: set[StaffId] = set()
        if (
            self._staff_qualification is not None
            and self._counselor_service is not None
        ):
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id, staff_id=finalizer_id
            )
            self._counselor_service.ensure_pharmacist(qualifications)
            qualified_staff_ids.add(finalizer_id)
        use_clock_as_counseling_time = False
        if counselor_id is None or counseled_at is None:
            if command.counseled_at is not None:
                counselor_id = finalizer_id
                counseled_at = CounselingTimestamp(command.counseled_at)
            elif record.source_system is None:
                use_clock_as_counseling_time = True
            else:
                raise MedicationHistoryDomainError(
                    "取込下書きを確定するには実際の指導日時が必要です。"
                )
            if (
                self._staff_qualification is not None
                and self._counselor_service is not None
            ):
                qualified_staff_ids.add(finalizer_id)
        elif command.counseled_at is not None and (
            CounselingTimestamp(command.counseled_at) != counseled_at
        ):
            raise MedicationHistoryDomainError(
                "記録済みの指導日時は確定時に変更できません。"
            )

        if not use_clock_as_counseling_time and (
            counselor_id is None or counseled_at is None
        ):
            raise MedicationHistoryDomainError(
                "薬歴を確定するには実際の指導者と指導日時が必要です。"
            )
        if (
            self._staff_qualification is not None
            and self._counselor_service is not None
            and finalizer_id not in qualified_staff_ids
        ):
            qualifications = await self._staff_qualification.get_qualifications(
                corporate_id=corporate_id, staff_id=finalizer_id
            )
            self._counselor_service.ensure_pharmacist(qualifications)

        if self._clock is None:
            raise MedicationHistoryDomainError(
                "薬歴確定日時を記録するClockが必要です。"
            )
        business_instant = business_now(self._clock)
        now = business_instant.astimezone(UTC)
        finalized_at = FinalizedTimestamp(now)
        if use_clock_as_counseling_time:
            counselor_id = finalizer_id
            counseled_at = CounselingTimestamp(now)

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

        if self._event_occurrence is not None:
            await self._event_occurrence.resolve_unknown_occurrence(
                corporate_id=corporate_id,
                event_id=record.event_id,
                occurred_at=command.event_occurred_at,
            )
        elif command.event_occurred_at is not None:
            raise MedicationHistoryDomainError(
                "Eventの発生日時を確認する保存境界がありません。"
            )

        finalized = record.finalize(
            counselor_id=counselor_id,
            counseled_at=counseled_at,
            finalized_at=finalized_at,
            finalized_by=finalizer_id,
            delay_reason=delay_reason,
            review_result=review_result,
        )
        finalized = await self._set_patient_retention_expiry(
            finalized, last_written_on=business_instant.date()
        )
        await self._projection_service.project(
            corporate_id=finalized.corporate_id,
            patient_id=finalized.patient_id,
        )
        return MedicationHistoryDto.from_entity(finalized)

    async def _set_patient_retention_expiry(
        self,
        finalized: MedicationHistoryRecord,
        *,
        last_written_on: date,
    ) -> MedicationHistoryRecord:
        """患者内の全確定記録を最新記入日から計算し、延長分を保存する。"""
        records = await self._record_repository.list_for_profile_projection(
            corporate_id=finalized.corporate_id,
            patient_id=finalized.patient_id,
        )
        patient_records: list[MedicationHistoryRecord] = []
        includes_finalized_record = False
        for record in records:
            if record.id == finalized.id:
                patient_records.append(finalized)
                includes_finalized_record = True
            else:
                patient_records.append(record)
        if not includes_finalized_record:
            patient_records.append(finalized)

        written_dates = [last_written_on]
        written_dates.extend(
            record.finalized_at.value.astimezone(BUSINESS_TIMEZONE).date()
            for record in patient_records
            if record.id != finalized.id
            and record.is_finalized
            and record.finalized_at is not None
        )
        latest_written_on = max(written_dates)
        catalog = PreservationPolicyCatalog.create_standard_statutory_catalog(
            PreservationRecordKind.MEDICATION_HISTORY
        )

        updated_finalized = finalized
        retention_expiry_updates: dict[MedicationHistoryRecordId, date] = {}
        for record in patient_records:
            if not record.is_finalized or record.finalized_at is None:
                continue
            updated = record.calculate_and_set_retention_expiry(
                catalog,
                last_written_on=latest_written_on,
            )
            if record.id == finalized.id:
                updated_finalized = updated
                await self._record_repository.save(updated)
            elif updated.retention_expiry_date != record.retention_expiry_date:
                expiry_date = updated.retention_expiry_date
                if expiry_date is None:
                    continue
                retention_expiry_updates[record.id] = expiry_date

        if retention_expiry_updates:
            await self._record_repository.update_retention_expiry_dates(
                corporate_id=finalized.corporate_id,
                patient_id=finalized.patient_id,
                expiry_dates=retention_expiry_updates,
            )
        return updated_finalized
