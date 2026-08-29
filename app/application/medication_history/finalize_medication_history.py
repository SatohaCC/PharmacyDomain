"""薬歴を確定し、頭書きへ投影するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.common import UnitOfWork
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.support import load_record_or_raise
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    MedicationHistoryRecord,
    MedicationHistoryRecordId,
    MedicationHistoryRepository,
    PatientMedicalProfile,
    PatientMedicalProfileRepository,
)


@dataclass(frozen=True, kw_only=True)
class FinalizeMedicationHistoryCommand:
    """薬歴確定の入力データ。"""

    corporate_id: str
    record_id: str


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
    ) -> None:
        self._record_repository = record_repository
        self._profile_repository = profile_repository
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work

    async def execute(
        self, command: FinalizeMedicationHistoryCommand
    ) -> MedicationHistoryDto:
        """SOAPの充足を集約に確認させてから確定し、頭書きへ投影する。"""
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
        finalized = record.finalize()
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
