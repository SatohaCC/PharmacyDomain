"""受付を薬歴へ明示的に関連付けるユースケース。"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.application.access_control.boundary import CorporateAccessBoundary
from app.application.access_control.models import Permission
from app.application.common.exceptions import NotFoundError
from app.application.common.unit_of_work import UnitOfWork
from app.application.reception.reference import MedicationHistoryAssociationBoundary
from app.domain.corporate.primitives import CorporateId
from app.domain.foundation.exceptions import DomainValidationError
from app.domain.medication_history.primitives import MedicationHistoryRecordId
from app.domain.reception.primitives import ReceptionId
from app.domain.reception.repository import ReceptionRepository
from app.domain.store.primitives import StoreId


@dataclass(frozen=True, kw_only=True)
class AssociateReceptionMedicationHistoryCommand:
    """薬剤師が受付の関連先として選んだ薬歴を表す。"""

    corporate_id: str
    store_id: str
    reception_id: str
    medication_history_id: str


@dataclass(frozen=True, kw_only=True)
class AssociateReceptionMedicationHistoryResultDto:
    """受付と薬歴の関連結果。"""

    reception_id: str
    medication_history_id: str


class AssociateReceptionMedicationHistoryUseCase:
    """保留中の受付情報を薬剤師が選んだ薬歴に関連付ける。"""

    def __init__(
        self,
        *,
        reception_repository: ReceptionRepository,
        medication_history_reference: MedicationHistoryAssociationBoundary,
        corporate_access: CorporateAccessBoundary,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._reception_repository = reception_repository
        self._medication_history_reference = medication_history_reference
        self._corporate_access = corporate_access
        self._unit_of_work = unit_of_work

    async def execute(
        self, command: AssociateReceptionMedicationHistoryCommand
    ) -> AssociateReceptionMedicationHistoryResultDto:
        """指定受付と薬歴を検証して関連付ける。"""
        self._unit_of_work.ensure_active()
        corporate_id = CorporateId.parse(command.corporate_id)
        await self._corporate_access.require_active(
            corporate_id=corporate_id,
            permission=Permission.MANAGE_RECEPTION,
        )
        store_id = StoreId.parse(command.store_id)
        reception_id = ReceptionId.parse(command.reception_id)
        reception = await self._reception_repository.get(
            corporate_id=corporate_id,
            store_id=store_id,
            reception_id=reception_id,
        )
        if reception is None:
            raise NotFoundError(
                "指定された受付が見つかりません。", code="RECEPTION_NOT_FOUND"
            )

        history_id = MedicationHistoryRecordId.parse(command.medication_history_id)
        history = await self._medication_history_reference.get_for_association(
            corporate_id=corporate_id,
            record_id=history_id,
        )
        if history is None:
            raise NotFoundError(
                "指定された薬歴が見つかりません。",
                code="MEDICATION_HISTORY_NOT_FOUND",
            )
        if reception.patient_id != history.patient_id:
            raise DomainValidationError(
                "受付と薬歴の患者が一致しないため、関連付けできません。"
            )
        if (
            reception.dispensing_id is not None
            and reception.dispensing_id != history.dispensing_id
        ) or (
            reception.prescription_id is not None
            and reception.prescription_id != history.prescription_id
        ):
            raise DomainValidationError(
                "受付と薬歴の調剤・処方が一致しないため、関連付けできません。"
            )
        if (
            reception.medication_history_id is not None
            and reception.medication_history_id != history.id
        ):
            raise DomainValidationError(
                "受付は別の薬歴に関連付いているため、付け替えできません。"
            )

        associated = replace(reception, medication_history_id=history.id)
        await self._reception_repository.save(associated)
        return AssociateReceptionMedicationHistoryResultDto(
            reception_id=str(associated.id.value),
            medication_history_id=str(history.id.value),
        )
