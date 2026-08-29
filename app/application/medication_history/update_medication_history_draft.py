"""下書きの薬歴を編集するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control import CorporateAccessBoundary, Permission
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import ProfileUpdateInput, SoapInput
from app.application.medication_history.support import (
    build_profile_updates,
    build_soap,
    load_record_or_raise,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history import (
    MedicationHistoryRecordId,
    MedicationHistoryRepository,
)


@dataclass(frozen=True, kw_only=True)
class UpdateMedicationHistoryDraftCommand:
    """下書き編集の入力データ。"""

    corporate_id: str
    record_id: str
    soap: SoapInput
    profile_updates: ProfileUpdateInput | None = None


class UpdateMedicationHistoryDraftUseCase:
    """下書きのSOAPと頭書き差分を差し替える。

    確定済の薬歴は集約が拒否する（``MedicationHistoryAlreadyFinalizedError``）。
    調剤録は3年保存であり、遡って書き換えられる記録は監査に耐えない。
    """

    def __init__(
        self,
        repository: MedicationHistoryRepository,
        corporate_access: CorporateAccessBoundary,
    ) -> None:
        self._repository = repository
        self._corporate_access = corporate_access

    async def execute(
        self, command: UpdateMedicationHistoryDraftCommand
    ) -> MedicationHistoryDto:
        """SOAPと頭書き差分を保存する。"""
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_MEDICATION_HISTORY,
        )
        record = await load_record_or_raise(
            self._repository,
            corporate_id=corporate_id,
            record_id=MedicationHistoryRecordId.parse(command.record_id),
        )
        record = record.update_draft_soap(build_soap(command.soap))
        record = record.update_draft_profile_updates(
            build_profile_updates(command.profile_updates)
        )
        await self._repository.save(record)
        return MedicationHistoryDto.from_entity(record)
