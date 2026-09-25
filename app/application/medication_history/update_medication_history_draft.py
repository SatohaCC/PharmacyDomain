"""下書きの薬歴を編集するユースケース。"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.medication_history.get_medication_history import (
    MedicationHistoryDto,
)
from app.application.medication_history.inputs import (
    BillingAdditionInput,
    CategorizedNoteInput,
    HandbookStatusInput,
    ProfileUpdateInput,
    ResidualDrugInput,
    SoapInput,
)
from app.application.medication_history.support import (
    build_additional_notes,
    build_handbook_status,
    build_profile_updates,
    build_residual_drug,
    build_soap,
    load_record_or_raise,
    parse_enum,
)
from app.domain.corporate.primitives import CorporateId
from app.domain.medication_history.primitives import (
    BillingAdditionCode,
    BillingAdditionName,
    CounselingMethod,
    MedicationHistoryRecordId,
)
from app.domain.medication_history.repository import MedicationHistoryRepository
from app.domain.medication_history.value_objects import BillingAddition


@dataclass(frozen=True, kw_only=True)
class UpdateMedicationHistoryDraftCommand:
    """下書き編集の入力データ。"""

    corporate_id: str
    record_id: str
    soap: SoapInput | None = None
    profile_updates: ProfileUpdateInput | None = None
    method: str | None = None
    handbook_status: HandbookStatusInput | None = None
    residual_drug: ResidualDrugInput | None = None
    information_sheet_provided: bool | None = None
    additional_notes: tuple[CategorizedNoteInput, ...] | None = None
    billing_additions: tuple[BillingAdditionInput, ...] | None = None


class UpdateMedicationHistoryDraftUseCase:
    """下書きの全項目（指導方法、SOAP、お薬手帳、残薬、情報提供文書、頭書き差分、追加メモ）を差し替える。

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
        """下書きを更新して保存する。"""
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
        method = (
            parse_enum(CounselingMethod, command.method, "服薬指導方法")
            if command.method is not None
            else None
        )
        soap = build_soap(command.soap) if command.soap is not None else None
        handbook_status = (
            build_handbook_status(command.handbook_status)
            if command.handbook_status is not None
            else None
        )
        residual_drug = (
            build_residual_drug(command.residual_drug)
            if command.residual_drug is not None
            else None
        )
        profile_updates = (
            build_profile_updates(command.profile_updates)
            if command.profile_updates is not None
            else None
        )
        additional_notes = (
            build_additional_notes(command.additional_notes)
            if command.additional_notes is not None
            else None
        )
        billing_additions = (
            tuple(
                BillingAddition(
                    code=BillingAdditionCode(item.code),
                    name=BillingAdditionName(item.name),
                    points=item.points,
                    quantity=item.quantity,
                )
                for item in command.billing_additions
            )
            if command.billing_additions is not None
            else None
        )

        record = record.update_draft(
            method=method,
            soap=soap,
            handbook_status=handbook_status,
            residual_drug=residual_drug,
            information_sheet_provided=command.information_sheet_provided,
            profile_updates=profile_updates,
            additional_notes=additional_notes,
            billing_additions=billing_additions,
        )
        await self._repository.save(record)
        return MedicationHistoryDto.from_entity(record)
